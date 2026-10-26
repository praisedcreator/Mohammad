"""Offline guardrails for this lab's compiled ARM template; no Azure requests."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent


def validate(template):
    resources=template.get('resources')
    if not isinstance(resources,list):raise ValueError('Expected a compiled ARM resources list.')
    def one(kind):
        matches=[r for r in resources if r.get('type')==kind]
        if len(matches)!=1:raise ValueError(f'Expected one {kind}.')
        return matches[0]
    storage=one('Microsoft.Storage/storageAccounts')['properties']
    required={'supportsHttpsTrafficOnly':True,'minimumTlsVersion':'TLS1_2','allowBlobPublicAccess':False,
              'allowSharedKeyAccess':False,'defaultToOAuthAuthentication':True,'publicNetworkAccess':'Disabled'}
    for key,expected in required.items():
        if storage.get(key)!=expected:raise ValueError(f'Storage guardrail failed: {key}')
    acl=storage.get('networkAcls',{})
    if acl.get('defaultAction')!='Deny' or acl.get('bypass')!='None':raise ValueError('Storage network access must default to deny without bypass.')
    encryption=storage.get('encryption',{})
    if encryption.get('keySource')!='Microsoft.Storage' or encryption.get('services',{}).get('blob',{}).get('enabled') is not True:
        raise ValueError('Blob encryption must be enabled.')
    container=one('Microsoft.Storage/storageAccounts/blobServices/containers')
    if container['properties'].get('publicAccess')!='None':raise ValueError('The blob container must remain private.')
    network=one('Microsoft.Network/virtualNetworks')
    if len(network['properties'].get('subnets',[]))<2:raise ValueError('Separate endpoint and workload subnets are required.')
    endpoint=one('Microsoft.Network/privateEndpoints')['properties']
    connections=endpoint.get('privateLinkServiceConnections',[])
    if len(connections)!=1 or connections[0].get('properties',{}).get('groupIds')!=['blob']:
        raise ValueError('The private endpoint must target blob storage.')
    if 'Microsoft.Storage/storageAccounts' not in connections[0]['properties'].get('privateLinkServiceId',''):
        raise ValueError('The endpoint must reference the storage account.')
    if 'Microsoft.Network/virtualNetworks/subnets' not in endpoint.get('subnet',{}).get('id',''):
        raise ValueError('The private endpoint must reference a VNet subnet.')
    zone=one('Microsoft.Network/privateDnsZones')
    if 'privatelink.blob.' not in zone.get('name',''):raise ValueError('Use the blob Private Link DNS zone.')
    link=one('Microsoft.Network/privateDnsZones/virtualNetworkLinks')['properties']
    if link.get('registrationEnabled') is not False or 'Microsoft.Network/virtualNetworks' not in link.get('virtualNetwork',{}).get('id',''):
        raise ValueError('A private DNS link to the VNet is required.')
    groups=one('Microsoft.Network/privateEndpoints/privateDnsZoneGroups')['properties'].get('privateDnsZoneConfigs',[])
    if not groups or 'Microsoft.Network/privateDnsZones' not in groups[0].get('properties',{}).get('privateDnsZoneId',''):
        raise ValueError('The endpoint must register with private DNS.')
    for output in template.get('outputs',{}).values():
        if any(secret in str(output).lower() for secret in ['listkeys(','listaccountsas(','listservicesas(']):
            raise ValueError('Deployment outputs must not expose storage credentials.')
    return {'result':'PASS','scope':'Compiled-template guardrails only; no live deployment or connectivity check'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiled',type=Path,default=ROOT/'main.json')
    parser.add_argument('--compare',type=Path)
    args=parser.parse_args()
    try:
        template=json.loads(args.compiled.read_text(encoding='utf-8-sig'))
        result=validate(template)
        if args.compare and template!=json.loads(args.compare.read_text(encoding='utf-8-sig')):
            raise ValueError('The committed ARM JSON differs from the freshly compiled Bicep source.')
        print(json.dumps(result,indent=2));return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
