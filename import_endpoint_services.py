import json
import os
import boto3
import uuid
import sys
sys.path.insert(0, './vendor')
import logging
from sts import establish_role
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def import_endpoint_services(event, context):
    dynamodb = boto3.resource('dynamodb')
    client = boto3.client('ec2')
    endpoint_service_table = dynamodb.Table(
        os.environ['DYNAMODB_TABLE_ENDPOINT_SERVICES'])
    accounts_table = dynamodb.Table(os.environ['DYNAMODB_TABLE_ACCOUNTS'])
    accounts = accounts_table.scan()['Items']
    endpoint_services = endpoint_service_table.scan()['Items']
    black_list_region = set('eu-west-3')
    regions = [region['RegionName']
               for region in client.describe_regions()['Regions']
               if region not in black_list_region]


    for region in regions:
        for acct in accounts:
            ACCESS_KEY, SECRET_KEY, SESSION_TOKEN = establish_role(acct)
            client = boto3.client('ec2',
                                  aws_access_key_id=ACCESS_KEY,
                                  aws_secret_access_key=SECRET_KEY,
                                  aws_session_token=SESSION_TOKEN,
                                  region_name=region
                                 )
            logger.info(
                'Looking up endpoint details on account {} in region {}'
                .format(acct['id'], region))
            endpoint_services = client.describe_vpc_endpoint_service_configurations()

            for endpoint_srv in endpoint_services['ServiceConfigurations']:
                service_id = endpoint_srv['ServiceId']
                service_name = endpoint_srv['ServiceName']
                acct_id = acct['id']
                service_state= endpoint_srv['ServiceState']
                acceptance_required = endpoint_srv['AcceptanceRequired']
                nlb_arns = endpoint_srv['NetworkLoadBalancerArns']

                logger.info(
                    'Recording Endpoint Service: {0} to nlbs {1} for account {2}'
                    .format(service_name, nlb_arns, acct)
                )

                response = endpoint_service_table.put_item(
                    Item={
                        'id': service_id,
                        'ServiceName': service_name,
                        'AccountID': acct_id,
                        'ServiceState': service_state,
                        'AcceptanceRequired': acceptance_required,
                        'NetworkLoadBalancerArns': nlb_arns,
                        'Region': region
                    }
                )
