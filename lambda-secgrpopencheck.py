import logging
import os
import json
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info(os.environ)
    logger.info('## EVENT')
    logger.info(event)
    try:
        security_group_rules = (event['detail']['requestParameters']['ipPermissions']['items'])
    except KeyError:
        logger.info('Security group rules not found in the event.')
        return
    logger.info(security_group_rules)
    cidr_violations = []
    security_group_identifier = []
    if "groupId" in event['detail']["requestParameters"]:
        security_group_identifier = (event['detail']["requestParameters"]["groupId"])
    elif "groupName" in event['detail']["requestParameters"]:
        security_group_identifier = (event['detail']["requestParameters"]["groupName"])
    else:
        logger.warning('No VPC Security Group ID or Classic Security Group Name Found.')

    for rule in security_group_rules:
        cidr_violations = ipv4_checks(security_group_identifier, rule,cidr_violations)
        cidr_violations = ipv6_checks(security_group_identifier, rule,cidr_violations)

    logger.info('## Its an SG EVENT')
    logger.info(cidr_violations)
    logger.info('## Completed')
    if cidr_violations:
        logger.info("Sending Violation for:" + str(json.dumps(cidr_violations, indent=2)))
        invoke_alert(event, context, cidr_violations)
        logger.info('Violated and Email Send')


def ipv4_checks(security_group_identifier, rule, cidr_violations):
    """IPv4 Checks."""
    try:
        for ipRange in rule['ipRanges']['items']:
            if ipRange['cidrIp'] == '0.0.0.0/0':
                logger.info('Violation - Contains IP/CIDR of 0.0.0.0/0')
                cidr_ip = ipRange["cidrIp"]
                logger.info(cidr_ip)
                create_violation_list(security_group_identifier, rule, cidr_ip, cidr_violations)

    except KeyError:
        logger.warning('There is not any Items under ipRanges')

    return cidr_violations


def ipv6_checks(security_group_identifier, rule, cidr_violations):
    """IPv4 Checks."""
    try:
        for ipv6Range in rule['ipv6Ranges']['items']:
            if ipv6Range['cidrIpv6'] == '::/0':
                logger.info('Violation - Contains CIDR IPv6 equal to ::/0')
                cidr_ip = ipv6Range["cidrIpv6"]
                logger.info(cidr_ip)
                create_violation_list(security_group_identifier, rule,
                                      cidr_ip, cidr_violations)

    except KeyError:
        logger.warning('There is not any Items under ipv6Ranges')

    return cidr_violations


def invoke_alert(event, context, cidr_violations):
    """Invoke Alerts and Actions."""
    logger.info('In Invoke Alerts')
    subject, message = create_non_compliance_message(event, cidr_violations)
    send_violation(context, subject, message)

def create_violation_list(security_group_identifier,rule, cidr_ip, cidr_violations):
    """Create Violation List."""
    cidr_violations.append({
        "groupIdentifier": security_group_identifier,
        "ipProtocol": rule["ipProtocol"],
        "toPort": rule["toPort"],
        "fromPort": rule["fromPort"],
        "cidrIp": cidr_ip
    })
    return cidr_violations

def create_non_compliance_message(event, cidr_violations):
    """Create Non Compliance Message."""
    logger.info("In Create Non Compliance Message")
    subject = "Violation - Security group rule contain a CIDR with /0!"
    message = "Violation - The following Security Group rules were in violation of the security group ingress policy and have an ingress rule with a CIDR of /0. \n\n"
    for resource in cidr_violations:
        message += 'Security Group Id: ' + resource["groupIdentifier"] + ' \n'
        message += 'IP Protocol: ' + resource["ipProtocol"] + ' \n'
        message += 'To Port: ' + str(resource["toPort"]) + ' \n'
        message += 'From Port: ' + str(resource["fromPort"]) + ' \n'
        message += 'CIDR IP: ' + str(resource["cidrIp"]) + ' \n'
        message += 'Account: ' + event['detail']['userIdentity']["accountId"]
        message += '\nRegion: ' + event['detail']["awsRegion"] + '\n\n\n'

    return subject, message


def send_violation(context, subject, message):
    """Send Violation Message."""
    outbound_topic_arn = 'arn:aws:sns:us-east-1:xxxxxxxxxxxxxxxx:Sample-Sns'
    findsnsregion = outbound_topic_arn.split(":")
    snsregion = findsnsregion[3]
    sendclient = boto3.client('sns', region_name=snsregion)
    message += "\n\n"
    message += ("This notification was generated by the Lambda function "
                + context.invoked_function_arn)
    try:
        sendclient.publish(
            TopicArn=outbound_topic_arn,
            Message=message,
            Subject=subject
        )
    except ClientError as err:
        print(err)
        return False
