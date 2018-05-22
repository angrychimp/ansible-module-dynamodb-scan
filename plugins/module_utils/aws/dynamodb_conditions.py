# -*- coding: utf-8 -*-
#
# Copyright (c) 2018 Randall Kahler
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.
#
# Author:
#   - Randall Kahler <rkahler@gmail.com>
#
# Common functionality to be used by the modules:
#   - dynamodb_scan_table_facts

"""
Common helper functions for DynamoDB facts modules
"""

try:
    import botocore
    from boto3.dynamodb import conditions
except ImportError:
    pass

class DynamoDbConditionsHelper(object):
    """ Provides DynamoDB Fact Services """
    def __init__(self, module):
        self.module = module
        
    def check_type(self, value):
        if type(value) is str:
            return {"S": value}
        if type(value) is int:
            return {"N": value}
        if type(value) is list:
            for i in list(range(0, len(value))):
                value[i] = self.check_type(value[i])
        return value
                
        
    def translate_filters(self, filter_list=[], **kwargs):
        try:
            join_type = kwargs['join_type'] if 'join_type' in kwargs else 'and'
            filters = False
            for f in filter_list:
                for k in f.keys():
                    if type(f[k]) is list:
                        # If the first item is a str, treat the whole
                        # thing as a list of values for an is_in() test
                        if type(f[k][0]) is str:
                            cond = conditions.Attr(k).is_in(self.check_type(f[k]))
                        else:
                            cond = self.translate_filters(f[k], join_type=k)
                    else:
                        if type(f[k]) is not dict:
                            # treat it as a simple "equals" comparison for the value
                            f[k] = {'value': f[k]}
                        if 'comparison_operator' not in f[k]:
                            f[k]['comparison_operator'] = 'eq'
                        if 'value' not in f[k]:
                            cond = eval("conditions.Attr(k)."+f[k]['comparison_operator']+"()")
                        else:
                            # Simple type translation
                            f[k]['value'] = self.check_type(f[k]['value'])
                            cond = eval("conditions.Attr(k)."+f[k]['comparison_operator']+"(f[k]['value'])")
                    if not filters:
                        filters = cond
                    else:
                        if join_type.lower() == 'or':
                            filters = filters|cond
                        else:
                            # Default to "AND"
                            filters = filters&cond
            return filters
        except botocore.exceptions.ClientError as e:
            self.module.fail_json_aws(e, msg="Error constructing filter condition objects")
        except SyntaxError as e:
            # Check to make sure the comparator exists
            if f[k]['comparison_operator'] not in dir(conditions.Attr):
                self.module.fail_json_aws(e, 'Comparison "%s" not a valid comparison_operator' % (f[k]['comparison_operator']))
            else:
                self.module.fail_json_aws(e, 'Error constructing filter condition objects')

    def build_filter_expression(self):
        filters = self.translate_filters(self.module.params['filter_expression'])
        try:
            builder = conditions.ConditionExpressionBuilder()
            return builder.build_expression(filters)
        except botocore.exceptions.ClientError as e:
            self.module.fail_json_aws(e, msg="Error building condition expression")

    def simplify(self, obj):
        # Takes a obj data set in DynamoDB format and
        # gets rid of the attribute type
        # e.g. Attr: {"S":"value"} becomes just Attr: "value"
        if type(obj) is list:
            for idx in list(range(0, len(obj))):
                if type(obj[idx]) in [dict, list]:
                    obj[idx] = self.simplify(obj[idx])
        elif type(obj) is dict:
            keys = obj.keys()
            if len(keys) == 1:
                obj = self.simplify(obj[keys[0]])
            else:
                for idx in list(range(0, len(keys))):
                    obj[keys[idx]] = self.simplify(obj[keys[idx]])
        return obj