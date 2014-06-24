# -*- coding: utf-8 -*-
#
# Copyright 2014 BigML
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


"""Options for BigMLer cluster

"""

def get_cluster_options(defaults={}, constants={}):
    """Adding arguments for the analyze subcommand

    """

    options = {
        # Make cluster public.
        '--public-cluster': {
            'action': 'store_true',
            'dest': 'public_dataset',
            'default': defaults.get('public_dataset', False),
            'help': "Make generated dataset public."},

        # Input fields to include in the cluster.
        '--cluster-fields': {
                "action": 'store',
                "dest": 'cluster_fields',
                "default": defaults.get('cluster_fields', None),
                "help": ("Comma-separated list of input fields"
                         " (predictors) to create the cluster.")}}

    return options