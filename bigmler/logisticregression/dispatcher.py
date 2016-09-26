# -*- coding: utf-8 -*-
#
# Copyright 2014-2016 BigML
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""BigMLer - cluster subcommand processing dispatching

"""
from __future__ import absolute_import

import sys
import os
import shutil

import bigml.api
import bigmler.utils as u
import bigmler.resources as r
import bigmler.pre_model_steps as pms
import bigmler.processing.args as a
import bigmler.processing.logisticregressions as plr
import bigmler.processing.sources as ps
import bigmler.processing.datasets as pd

from bigmler.defaults import DEFAULTS_FILE
from bigmler.lrprediction import lr_prediction, remote_lr_prediction
from bigmler.reports import clear_reports, upload_reports
from bigmler.command import get_stored_command
from bigmler.evaluation import evaluate
from bigmler.dispatcher import (SESSIONS_LOG, command_handling,
                                clear_log_files, get_test_dataset,
                                get_objective_id)

COMMAND_LOG = u".bigmler_logistic_regression"
DIRS_LOG = u".bigmler_logistic_regression_dir_stack"
LOG_FILES = [COMMAND_LOG, DIRS_LOG, u.NEW_DIRS_LOG]
MINIMUM_MODEL = "full=false"
DEFAULT_OUTPUT = u"predictions.csv"


def logistic_regression_dispatcher(args=sys.argv[1:]):
    """Parses command line and calls the different processing functions

    """

    # If --clear-logs the log files are cleared
    if "--clear-logs" in args:
        clear_log_files(LOG_FILES)

    command = command_handling(args, COMMAND_LOG)

    # Parses command line arguments.
    command_args = a.parse_and_check(command)
    default_output = ('evaluation' if command_args.evaluate
                      else 'predictions.csv')
    resume = command_args.resume
    if command_args.resume:
        command_args, session_file, output_dir = get_stored_command(
            args, command_args.debug, command_log=COMMAND_LOG,
            dirs_log=DIRS_LOG, sessions_log=SESSIONS_LOG)
        default_output = ('evaluation' if command_args.evaluate
                          else 'predictions.csv')
        if command_args.predictions is None:
            command_args.predictions = os.path.join(output_dir,
                                                    default_output)
    else:
        if command_args.output_dir is None:
            command_args.output_dir = a.NOW
        if command_args.predictions is None:
            command_args.predictions = os.path.join(command_args.output_dir,
                                                    default_output)
        if len(os.path.dirname(command_args.predictions).strip()) == 0:
            command_args.predictions = os.path.join(command_args.output_dir,
                                                    command_args.predictions)
        directory = u.check_dir(command_args.predictions)
        session_file = os.path.join(directory, SESSIONS_LOG)
        u.log_message(command.command + "\n", log_file=session_file)
        try:
            shutil.copy(DEFAULTS_FILE, os.path.join(directory, DEFAULTS_FILE))
        except IOError:
            pass
        u.sys_log_message(u"%s\n" % os.path.abspath(directory),
                          log_file=DIRS_LOG)

    # Creates the corresponding api instance
    api = a.get_api_instance(command_args, u.check_dir(session_file))

    # Selects the action to perform
    if (a.has_train(command_args) or a.has_test(command_args)
            or command_args.export_fields):
        output_args = a.get_output_args(api, command_args, resume)
        a.transform_args(command_args, command.flags, api,
                         command.user_defaults)
        compute_output(**output_args)
    u.log_message("_" * 80 + "\n", log_file=session_file)


def compute_output(api, args):
    """ Creates one or more models using the `training_set` or uses the ids
    of previously created BigML models to make predictions for the `test_set`.

    """

    logistic_regression = None
    logistic_regressions = None
    # no multi-label support at present

    # variables from command-line options
    resume = args.resume_
    logistic_regression_ids = args.logistic_regression_ids_
    output = args.predictions
    # there's only one logistic regression to be generated at present
    args.max_parallel_logistic_regressions = 1
    # logistic regressions cannot be published yet.
    args.public_logistic_regression = False

    # It is compulsory to have a description to publish either datasets or
    # logistic regressions
    if (not args.description_ and (args.public_logistic_regression or
                                   args.public_dataset)):
        sys.exit("You should provide a description to publish.")

    # When using --new-fields, it is compulsory to specify also a dataset
    # id
    if args.new_fields and not args.dataset:
        sys.exit("To use --new-fields you must also provide a dataset id"
                 " to generate the new dataset from it.")

    path = u.check_dir(output)
    session_file = u"%s%s%s" % (path, os.sep, SESSIONS_LOG)
    csv_properties = {}
    if args.objective_field:
        csv_properties.update({'objective_field': args.objective_field})
    # If logging is required set the file for logging
    log = None
    if args.log_file:
        u.check_dir(args.log_file)
        log = args.log_file
        # If --clear_logs the log files are cleared
        clear_log_files([log])

    # basic pre-model step: creating or retrieving the source related info
    source, resume, csv_properties, fields = pms.get_source_info(
        api, args, resume, csv_properties, session_file, path, log)
    # basic pre-model step: creating or retrieving the dataset related info
    dataset_properties = pms.get_dataset_info(
        api, args, resume, source,
        csv_properties, fields, session_file, path, log)
    (_, datasets, test_dataset,
     resume, csv_properties, fields) = dataset_properties
    if datasets:
        # Now we have a dataset, let's check if there's an objective_field
        # given by the user and update it in the fields structure
        args.objective_id_ = get_objective_id(args, fields)
    if args.logistic_file:
        # logistic regression is retrieved from the contents of the given local
        # JSON file
        logistic_regression, csv_properties, fields = u.read_local_resource(
            args.logistic_file,
            csv_properties=csv_properties)
        logistic_regressions = [logistic_regression]
        logistic_regression_ids = [logistic_regression['resource']]
    else:
        # logistic regression is retrieved from the remote object
        logistic_regressions, logistic_regression_ids, resume = \
            plr.logistic_regressions_processing( \
            datasets, logistic_regressions, logistic_regression_ids, \
            api, args, resume, fields=fields, \
            session_file=session_file, path=path, log=log)
        if logistic_regressions:
            logistic_regression = logistic_regressions[0]

    # We update the logistic regression's public state if needed
    if logistic_regression:
        if isinstance(logistic_regression, basestring):
            if not a.has_test(args):
                query_string = MINIMUM_MODEL
            elif args.export_fields:
                query_string = r.ALL_FIELDS_QS
            else:
                query_string = ''
            logistic_regression = u.check_resource(logistic_regression,
                                                   api.get_logistic_regression,
                                                   query_string=query_string)
        logistic_regressions[0] = logistic_regression
        if (args.public_logistic_regression or
                (args.shared_flag and r.shared_changed(args.shared,
                                                       logistic_regression))):
            logistic_regression_args = {}
            if args.shared_flag and r.shared_changed(args.shared,
                                                     logistic_regression):
                logistic_regression_args.update(shared=args.shared)
            if args.public_logistic_regression:
                logistic_regression_args.update( \
                    r.set_publish_logistic_regression_args(args))
            if logistic_regression_args:
                logistic_regression = r.update_logistic_regression( \
                    logistic_regression, logistic_regression_args, args,
                    api=api, path=path, \
                    session_file=session_file)
                logistic_regressions[0] = logistic_regression

    # We get the fields of the logistic_regression if we haven't got
    # them yet and need them
    if logistic_regression and (args.test_set or args.export_fields):
        fields = plr.get_logistic_fields( \
            logistic_regression, csv_properties, args)

    if fields and args.export_fields:
        fields.summary_csv(os.path.join(path, args.export_fields))

    # If predicting
    if logistic_regressions and (a.has_test(args) or \
            (test_dataset and args.remote)):
        if test_dataset is None:
            test_dataset = get_test_dataset(args)

        # Remote predictions: predictions are computed as batch predictions
        # in bigml.com except when --no-batch flag is set on
        if args.remote and not args.no_batch:
            # create test source from file
            test_name = "%s - test" % args.name
            if args.test_source is None:
                test_properties = ps.test_source_processing(
                    api, args, resume, name=test_name,
                    session_file=session_file, path=path, log=log)
                (test_source, resume,
                 csv_properties, test_fields) = test_properties
            else:
                test_source_id = bigml.api.get_source_id(args.test_source)
                test_source = api.check_resource(test_source_id)
            if test_dataset is None:
                # create test dataset from test source
                dataset_args = r.set_basic_dataset_args(args, name=test_name)
                test_dataset, resume = pd.alternative_dataset_processing(
                    test_source, "test", dataset_args, api, args,
                    resume, session_file=session_file, path=path, log=log)
            else:
                test_dataset_id = bigml.api.get_dataset_id(test_dataset)
                test_dataset = api.check_resource(test_dataset_id)

            csv_properties.update(objective_field=None,
                                  objective_field_present=False)
            test_fields = pd.get_fields_structure(test_dataset,
                                                  csv_properties)
            batch_prediction_args = r.set_batch_prediction_args(
                args, fields=fields,
                dataset_fields=test_fields)

            remote_lr_prediction(logistic_regression, test_dataset, \
                batch_prediction_args, args, \
                api, resume, prediction_file=output, \
                session_file=session_file, path=path, log=log)

        else:
            lr_prediction(logistic_regressions, fields, args,
                          session_file=session_file)

    # If evaluate flag is on, create remote evaluation and save results in
    # json and human-readable format.
    if args.evaluate:
        # When we resume evaluation and models were already completed, we
        # should use the datasets array as test datasets
        if args.has_test_datasets_:
            test_dataset = get_test_dataset(args)
        if args.dataset_off and not args.has_test_datasets_:
            args.test_dataset_ids = datasets
        if args.test_dataset_ids and args.dataset_off:
            # Evaluate the models with the corresponding test datasets.
            test_dataset_id = bigml.api.get_dataset_id( \
                args.test_dataset_ids[0])
            test_dataset = api.check_resource(test_dataset_id)
            csv_properties.update(objective_field=None,
                                  objective_field_present=False)
            test_fields = pd.get_fields_structure(test_dataset,
                                                  csv_properties)
            resume = evaluate(logistic_regressions, args.test_dataset_ids, api,
                              args, resume,
                              fields=fields, dataset_fields=test_fields,
                              session_file=session_file, path=path,
                              log=log,
                              objective_field=args.objective_field)

    u.print_generated_files(path, log_file=session_file,
                            verbosity=args.verbosity)
    if args.reports:
        clear_reports(path)
        if args.upload:
            upload_reports(args.reports, path)
