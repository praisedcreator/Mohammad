from copy import deepcopy
import json
from pathlib import Path
import unittest
from validate import validate

TEMPLATE=json.loads((Path(__file__).parent/'main.json').read_text(encoding='utf-8-sig'))


class StorageGuardrailTests(unittest.TestCase):
    def resource(self,template,kind):return next(r for r in template['resources'] if r['type']==kind)

    def test_compiled_template_passes(self):self.assertEqual(validate(TEMPLATE)['result'],'PASS')

    def test_public_storage_network_rejected(self):
        t=deepcopy(TEMPLATE);self.resource(t,'Microsoft.Storage/storageAccounts')['properties']['publicNetworkAccess']='Enabled'
        with self.assertRaises(ValueError):validate(t)

    def test_shared_keys_rejected(self):
        t=deepcopy(TEMPLATE);self.resource(t,'Microsoft.Storage/storageAccounts')['properties']['allowSharedKeyAccess']=True
        with self.assertRaises(ValueError):validate(t)

    def test_public_container_rejected(self):
        t=deepcopy(TEMPLATE);self.resource(t,'Microsoft.Storage/storageAccounts/blobServices/containers')['properties']['publicAccess']='Blob'
        with self.assertRaises(ValueError):validate(t)

    def test_disabled_encryption_rejected(self):
        t=deepcopy(TEMPLATE);self.resource(t,'Microsoft.Storage/storageAccounts')['properties']['encryption']['services']['blob']['enabled']=False
        with self.assertRaises(ValueError):validate(t)

    def test_wrong_endpoint_service_rejected(self):
        t=deepcopy(TEMPLATE);self.resource(t,'Microsoft.Network/privateEndpoints')['properties']['privateLinkServiceConnections'][0]['properties']['groupIds']=['file']
        with self.assertRaises(ValueError):validate(t)

    def test_missing_dns_zone_link_rejected(self):
        t=deepcopy(TEMPLATE);t['resources']=[r for r in t['resources'] if r['type']!='Microsoft.Network/privateDnsZones/virtualNetworkLinks']
        with self.assertRaises(ValueError):validate(t)

    def test_missing_endpoint_dns_registration_rejected(self):
        t=deepcopy(TEMPLATE);self.resource(t,'Microsoft.Network/privateEndpoints/privateDnsZoneGroups')['properties']['privateDnsZoneConfigs']=[]
        with self.assertRaises(ValueError):validate(t)

    def test_credential_outputs_rejected(self):
        t=deepcopy(TEMPLATE);t['outputs']['secret']={'type':'string','value':"[listKeys(resourceId('Microsoft.Storage/storageAccounts', variables('storageName')), '2023-05-01')]"}
        with self.assertRaises(ValueError):validate(t)


if __name__=='__main__':unittest.main()
