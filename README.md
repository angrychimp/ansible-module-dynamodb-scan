# ansible-module-dynamodb-scan
An Ansible module to pull "facts" from an AWS DynamoDB table

To install, perform the following:
```
curl -O https://raw.githubusercontent.com/angrychimp/ansible-module-dynamodb-scan/master/install-dynamodb-ansible-module.yml && ansible-playbook install-dynamodb-ansible-module.yml
```

This will install the module into your user module folder.

## Requirements
This module requires:
1. `boto3` and `botocore` installed
2. That you already have an AWS account, and API access
3. That you have your API keys set in `~/.aws/credentials` or know how to configure API access in an Ansible playbook
4. That you have access to a DynamoDB table already created which you can scan

Assuming the above are met, you can test that the module is functional by running:
```
ansible localhost -m dynamodb_scan_table_facts -a 'table_name=TestTable limit=1'
```

The result should be a single record from your table. Further examples demonstrating use of the module include the following.

```
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
```