from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from app import handler, item_for, normalise_record, parse_event, process_event

SAMPLE=json.loads((Path(__file__).parent/'sample-event.json').read_text())


class IntakeTests(unittest.TestCase):
    def test_url_decoding_and_stable_identity(self):
        record=normalise_record(SAMPLE['Records'][0])
        self.assertEqual(record['key'],'incoming/practice report.txt')
        changed=deepcopy(SAMPLE['Records'][0]);changed['s3']['object']['sequencer']='af'
        self.assertEqual(normalise_record(changed)['event_id'],record['event_id'])

    def test_new_version_is_a_separate_event(self):
        record=deepcopy(SAMPLE['Records'][0]);first=normalise_record(record)
        record['s3']['object']['versionId']='practice-version-2'
        self.assertNotEqual(normalise_record(record)['event_id'],first['event_id'])

    def test_empty_and_wrong_event_types_rejected(self):
        for event in [{},{'Records':[]},{'Records':{}},{'Records':[{'eventSource':'sns'}]}]:
            with self.subTest(event=event),self.assertRaises(ValueError):parse_event(event)

    def test_negative_boolean_or_fractional_size_rejected(self):
        for size in [-1,True,1.2]:
            record=deepcopy(SAMPLE['Records'][0]);record['s3']['object']['size']=size
            with self.subTest(size=size),self.assertRaises(ValueError):normalise_record(record)

    def test_invalid_encoded_keys_rejected(self):
        for key in ['bad%ZZ','bad%FF','', 'x'*1025]:
            record=deepcopy(SAMPLE['Records'][0]);record['s3']['object']['key']=key
            with self.subTest(key=key),self.assertRaises(ValueError):normalise_record(record)

    def test_missing_fields_and_bad_sequence_rejected(self):
        for field in ['key','size','sequencer']:
            record=deepcopy(SAMPLE['Records'][0]);del record['s3']['object'][field]
            with self.subTest(field=field),self.assertRaises(ValueError):normalise_record(record)
        record=deepcopy(SAMPLE['Records'][0]);record['s3']['object']['sequencer']='not-hex'
        with self.assertRaises(ValueError):normalise_record(record)

    def test_deletion_event_rejected(self):
        record=deepcopy(SAMPLE['Records'][0]);record['eventName']='ObjectRemoved:Delete'
        with self.assertRaises(ValueError):normalise_record(record)

    def test_whole_batch_validates_before_writing(self):
        class NoWrites:
            def put_item(self,**kwargs):raise AssertionError('no writes expected')
        with self.assertRaises(ValueError):process_event({'Records':SAMPLE['Records']+[{}]},NoWrites(),'practice-table')

    def test_real_sdk_conditional_put_contract(self):
        import boto3
        from botocore.stub import Stubber
        client=boto3.client('dynamodb',region_name='us-east-1',aws_access_key_id='unit-test',aws_secret_access_key='unit-test')
        expected={'TableName':'practice-table','Item':item_for(parse_event(SAMPLE)[0]),'ConditionExpression':'attribute_not_exists(pk)'}
        with Stubber(client) as stub:
            stub.add_response('put_item',{},expected)
            self.assertEqual(process_event(SAMPLE,client,'practice-table'),{'received':1,'written':1,'duplicates':0})
            stub.assert_no_pending_responses()

    def test_duplicate_delivery_does_not_write_again(self):
        import boto3
        from botocore.stub import Stubber
        client=boto3.client('dynamodb',region_name='us-east-1',aws_access_key_id='unit-test',aws_secret_access_key='unit-test')
        with Stubber(client) as stub:
            stub.add_client_error('put_item',service_error_code='ConditionalCheckFailedException')
            self.assertEqual(process_event(SAMPLE,client,'practice-table')['duplicates'],1)

    def test_service_error_is_not_reported_as_duplicate(self):
        import boto3
        from botocore.exceptions import ClientError
        from botocore.stub import Stubber
        client=boto3.client('dynamodb',region_name='us-east-1',aws_access_key_id='unit-test',aws_secret_access_key='unit-test')
        with Stubber(client) as stub:
            stub.add_client_error('put_item',service_error_code='AccessDeniedException')
            with self.assertRaises(ClientError):process_event(SAMPLE,client,'practice-table')

    def test_handler_requires_configuration_before_client_creation(self):
        with patch.dict('os.environ',{'TABLE_NAME':''}),self.assertRaises(ValueError):handler(SAMPLE,None)


if __name__=='__main__':unittest.main()
