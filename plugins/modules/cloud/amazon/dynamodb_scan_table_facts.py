#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: dynamodb_scan_table_facts
short_description: Gather facts from a DynamoDB table scan.
description:
    - Gatther facts from a DynamoDB table using the `scan()` function.
    - Returns a list of items resulting from the scan.
version_added: "2.5"
requirements: [ boto3 ]
author: "Randall Kahler (@angrychimp)"
options:
  table_name:
    description:
      - The name of the table containing the requested items
    required: true
  index_name:
    description:
      - The name of a secondary index to scan
      - This index can be any local secondary index or global secondary index
  limit:
    description:
      - The maximum number of items to evaluate
      - (Not necessarily the number of matching items)
  select:
    description:
      - The attributes to be returned in the result
      - You can retrieve all item attributes, specific item attributes, the count of matching items, or in the case of an index, some or all of the attributes projected into the index.
      - If C(projection_expression) is defined, this may only be be C(SPECIFIC_ATTRIBUTES) (or omitted)
    choices: ['ALL_ATTRIBUTES', 'ALL_PROJECTED_ATTRIBUTES', 'COUNT', 'SPECIFIC_ATTRIBUTES']
    default: 'ALL_ATTRIBUTES'
  projection_expression:
    description:
      - A list of one or more attributes to retrieve from the specified table or index.
      - These attributes can include scalars, sets, or elements of a JSON document.
  filter_expression:
    description:
      - A list of dictionaries describing filters to apply to the scan result set.
      - By default, filters are inclusive (filterA AND filterB), but nested lists may be excluded (OR).
      - Values must conform to the attribute specification for DynamoDB attributes (see examples).
      - As these are nested dictionaries, pay close attention to indentation requirements (C(comparison_operator) and C(value) are double-indented under an attribute key).
notes:
  - Additional information on options (such as filter conditions and functions), please review the online documentation.
  - https://boto3.readthedocs.io/en/latest/guide/dynamodb.html#querying-and-scanning

extends_documentation_fragment:
    - aws
    - dynamodb_table
'''

EXAMPLES = '''
# Note: These examples do not set authentication details, see the AWS Guide for details.

# Gather all facts from a DynamoDB table
- dynamodb_scan_table_facts:
  table_name: MyTable

# Gather specific attributes from a table
- dynamodb_scan_table_facts:
  table_name: Contacts
  projection_expression:
    - FirstName
    - LastName
    - EmailAddress

# Filter results from a scan
- dynamodb_scan_table_facts:
  table_name: Servers
  projection_expression:
    - PrivateIpAddress
    - SerialNumber
  filter_expression:
    - Location:
        comparison_operator: eq
        value:
            S: datacenter

# Filters default to "equals", and values are assumed to be strings
# The below task accomplishes the same as the example immediately above
- dynamodb_scan_table_facts:
  table_name: Servers
  projection_expression: "PrivateIpAddress, SerialNumber"
  filter_expression:
    - Location: datacenter
    
# Same as above, but return "simplified" results
# (DynamoDB attribute type is stripped; a simple dict is returned)
- dynamodb_scan_table_facts:
  table_name: Servers
  simplify: True
  projection_expression: "PrivateIpAddress, SerialNumber"
  filter_expression:
    - Location: datacenter

# Mutually exclusive criteria
# (20 < GradePercentage > 80)
- dynamodb_scan_table_facts:
  table_name: Students
  projection_expression:
    - Name
    - GradePercentage
  filter_expression:
    - OR:
      - GradePercentage:
          comparison_operator: lt
          value: 20
      - GradePercentage:
          comparison_operator: gt
          value: 80
  register: passers_and_failers

# Complex search criteria
# (ProjectGroup is "Phoenix" or "Pegasus",
#  or Location is Houston) AND (LaunchGroup is "green"
#  or Level is "Manager" or "Director")
- dynamodb_scan_table_facts:
  table_name: Developers
  projection_expression:
    - Name
    - "RegisteredInstances[0]"
    - EmailAddress
  filter_expression:
    - OR:
      - ProjectGroup:
          comparison_operator: is_in
          value:
            - Phoenix
            - Pegasus
      - Location: Houston
    - AND:
      - OR:
        - LaunchGroup: green
        - Level:
          - Manager
          - Director
'''

RETURN = '''
Items:
    description: List of Item dictionaries, containing DynamoDB Attribute structs. (List may be empty if no objects match filters.)
    type: list
    returned: always
    sample: [
        {
            "AttributeA": { "S": "ValueA" },
            "AttributeList": {
                "L": [
                    { "S": "ListItem1" },
                    { "S": "ListItem2"
                ]
            }
        }
    ]
'''

import traceback

try:
    from botocore.exceptions import (ClientError, ParamValidationError)
except ImportError:
    pass  # caught by imported HAS_BOTO3

from ansible.module_utils.aws.core import AnsibleAWSModule
from ansible.module_utils.ec2 import (ec2_argument_spec, boto3_conn, HAS_BOTO3, get_aws_connection_info,
                                      boto3_tag_list_to_ansible_dict, ansible_dict_to_boto3_filter_list,
                                      camel_dict_to_snake_dict, snake_dict_to_camel_dict)
from ansible.module_utils.aws.dynamodb_conditions import DynamoDbConditionsHelper

def main():
    argument_spec = ec2_argument_spec()
    scan_args = dict(
        table_name=dict(required=True, type='str'),
        index_name=dict(type='str'),
        limit=dict(type='int'),
        projection_expression=dict(type='list'),
        filter_expression=dict(type='list')
    )
    argument_spec.update(scan_args)
    argument_spec.update(dict(simplify=dict(type='bool')))

    module = AnsibleAWSModule(argument_spec=argument_spec,
                           supports_check_mode=True)

    if not HAS_BOTO3:
        module.fail_json(msg='boto3 required for this module')

    region, ec2_url, aws_connect_params = get_aws_connection_info(module, boto3=True)
    
    if region:
        connection = boto3_conn(
            module,
            conn_type='client',
            resource='dynamodb',
            region=region,
            endpoint=ec2_url,
            **aws_connect_params
        )
    else:
        module.fail_json(msg="region must be specified")
    
    try:
        args = {}
        for k, v in list(module.params.items()):
            if v and k in scan_args.keys():
                args[k] = v
        args = snake_dict_to_camel_dict(args, True)
        helper = DynamoDbConditionsHelper(module)
        
        if module.params['filter_expression'] and type(module.params['filter_expression']) is list:
            expression = helper.build_filter_expression()
            args['FilterExpression'] = expression.condition_expression
            args['ExpressionAttributeNames'] = expression.attribute_name_placeholders
            args['ExpressionAttributeValues'] = expression.attribute_value_placeholders
        
        if args['ProjectionExpression'] and type(args['ProjectionExpression']) is list:
            args['ProjectionExpression'] = ", ".join(args['ProjectionExpression'])
        
        result = connection.scan(**args)['Items']
        if 'simplify' in module.params.keys() and module.params['simplify']:
            result = helper.simplify(result)
    except ClientError as e:
        module.fail_json(msg=e.message, exception=traceback.format_exc())
    except ParamValidationError as e:
        msg = e.message + "\nexpression = " + str(expression)
        module.fail_json(msg=msg, exception=traceback.format_exc())
    
    module.exit_json(Items=result)
    
if __name__ == '__main__':
    main()