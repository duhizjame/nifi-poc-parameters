import nipyapi
from collections import namedtuple
from nipyapi.registry.models.versioned_flow_snapshot import VersionedFlowSnapshot
from nipyapi.registry.models.versioned_process_group import VersionedProcessGroup
from nipyapi.registry.models.versioned_parameter_context import VersionedParameterContext
from nipyapi.registry.models.versioned_parameter import VersionedParameter
import json
import time

def create_or_update_parameter_context(ctx: VersionedParameterContext):
    import yaml

    conf = yaml.load("""
name: TestProcessGroupParameterContext
inherits: Core
values:
- name: testValue
    value: value1
    isControllerService: false
- name: AvroReaderPGLevel
    value: d040203c-018b-1000-239a-13d7f197ba3b
    isControllerService: true
- name: AvroWriterPGLevel
    value: d0401235-018b-1000-7508-b7eaa58a5f67
    isControllerService: true
""")

    param: VersionedParameter
    for param in ctx.parameters:
        param.value = conf["values"][param.name]["value"]
    return ctx

# disable TLS check, do at your own risk
nipyapi.config.nifi_config.verify_ssl = False
nipyapi.config.registry_config.verify_ssl = False

# connect to Nifi
nipyapi.utils.set_endpoint("http://localhost:8082/nifi-api")
# wait for connection to be set up
connected = nipyapi.utils.wait_to_complete(
    test_function=nipyapi.utils.is_endpoint_up,
    endpoint_url="http://localhost:8082/nifi",
    nipyapi_delay=nipyapi.config.long_retry_delay,
    nipyapi_max_wait=nipyapi.config.short_max_wait
)

# connect to Nifi Registry
nipyapi.utils.set_endpoint("http://localhost:19090/nifi-registry-api")
connected = nipyapi.utils.wait_to_complete(
    test_function=nipyapi.utils.is_endpoint_up,
    endpoint_url="http://localhost:19090/nifi-registry",
    nipyapi_delay=nipyapi.config.long_retry_delay,
    nipyapi_max_wait=nipyapi.config.short_max_wait
)

print("connected")

from nipyapi import versioning

# define the list of Process Groups
process_groups = [ "MyProcessGroup" ]

# store exported flows
exported_flows = {}
ExportedFlow = namedtuple("ExportedFlow", ["name", "bucket_name", "definition"])

for pgn in process_groups:
    # make sure there's a Process Group on the Canvas
    pg = nipyapi.canvas.get_process_group(pgn, greedy=False)
    
    if pg is None:
        print(F"process group {pgn} was not found in the Nifi Canvas")
        exit(1)
  
    # make sure the process group is in the Registry
    if pg.component.version_control_information is None:
        print(F"process group {pgn} is not added to version control")
        exit(1)
  
    # make sure there are no uncommitted changes on the Canvas
    diff = nipyapi.nifi.apis.process_groups_api.ProcessGroupsApi().get_local_modifications(pg.id)
    diffn = len(diff.component_differences)
    if diffn > 0:
        print(F"there are uncommitted changes in the process group {pgn}")
        exit(1)
  
    
    # since we are here, we found no issue with this Process Group
    # let's export it
  
    bucket_id = pg.component.version_control_information.bucket_id
    bucket_name = pg.component.version_control_information.bucket_name
    flow_id = pg.component.version_control_information.flow_id
    flow_name = pg.component.version_control_information.flow_name

    print(F"Found flow: {flow_name} with id: {flow_id} under bucket: {bucket_name} with id: {bucket_id}")

    # export the latest version from the Registry
    flow_json = versioning.get_flow_version(bucket_id, flow_id, version=None)
    
    exported_flows[pgn] = ExportedFlow(pgn, bucket_name, flow_json)

# connect to Nifi
nipyapi.utils.set_endpoint("http://localhost:8083/nifi-api")
# wait for connection to be set up
connected = nipyapi.utils.wait_to_complete(
    test_function=nipyapi.utils.is_endpoint_up,
    endpoint_url="http://localhost:8083/nifi",
    nipyapi_delay=nipyapi.config.long_retry_delay,
    nipyapi_max_wait=nipyapi.config.short_max_wait
)

# connect to Nifi Registry
nipyapi.utils.set_endpoint("http://localhost:19091/nifi-registry-api")
connected = nipyapi.utils.wait_to_complete(
    test_function=nipyapi.utils.is_endpoint_up,
    endpoint_url="http://localhost:19091/nifi-registry",
    nipyapi_delay=nipyapi.config.long_retry_delay,
    nipyapi_max_wait=nipyapi.config.short_max_wait
)

# check if the Bucket already exists
bucket = versioning.get_registry_bucket(bucket_name)

if bucket is None:
  bucket = versioning.create_registry_bucket(bucket_name)


for flow_name, exported_flow in exported_flows.items():
    bucket = versioning.get_registry_bucket(exported_flow.bucket_name)

    pg = nipyapi.canvas.get_process_group(flow_name, greedy=False)
    if pg is not None:
        print(F"Process group exists on Canvas, but not in Registry with a new version?: {flow_name}")
        # exit(1)
    else:
        bflow = versioning.get_flow_in_bucket(bucket.identifier, flow_name)
        pg = nipyapi.canvas.get_process_group(flow_name, greedy=False)

        if bflow is None and pg is not None:
            print(F"Process group exists on Canvas, but not in Registry: {flow_name}")
            exit(1)

        print(F"Process group does not exist on Canvas and not in Registry: {flow_name}")
        if bflow is not None and pg is not None:
            diff = nipyapi.nifi.apis.process_groups_api.ProcessGroupsApi().get_local_modifications(pg.id)
            diffn = len(diff.component_differences)
            if diffn > 0:
                print(F"There are uncommitted changes in the process group {pgn}")
                exit(1)

def sanitize_pg(pg_def: VersionedProcessGroup) -> VersionedProcessGroup:
    # sanitize the processGroup section from parameterContext references, does a
    # recursive cleanup of the processGroups if multiple levels are found.


    if pg_def.parameter_context_name is not None:
        pg_def.parameter_context_name = None

    if pg_def.process_groups is None or len(pg_def.process_groups) == 0:
        return pg_def

    for pg in pg_def.process_groups:
        sanitize_pg(pg)
    return pg

# get the registry client for the test environment, we need this to import
# process groups
reg_clients = versioning.list_registry_clients()
test_reg_client = None

# just getting the first registry client we find, assuming we only have one
for reg_client in reg_clients.registries:
    test_reg_client = reg_client.component
    break

print(F"Found test registry client: {test_reg_client.name} -> {test_reg_client.uri}")

# read the Canvas root element ID to attach Process Groups
root_pg = nipyapi.canvas.get_root_pg_id()

for flow_name, exported_flow in exported_flows.items():

    flow: VersionedFlowSnapshot = exported_flow.definition

    # get the bucket details
    bucket = versioning.get_registry_bucket(exported_flow.bucket_name)
    bucket_identifier = bucket.identifier

    # remove from top level Process Group
    if flow.parameter_contexts is not None:
        param_ctx = flow.parameter_contexts
        flow.parameter_contexts = None
        flow_contents: VersionedProcessGroup = flow.flow_contents
        if flow_contents.parameter_context_name is not None:
            flow_contents.parameter_context_name = None
        # additionally, sanitize inner Process Groups
        process_groups: list[VersionedProcessGroup] = flow_contents.process_groups
        for pg in process_groups:
            sanitize_pg(pg)
        flow_contents.process_groups = process_groups
        flow.flow_contents = flow_contents
    

    # json_sanitized_flow = json.dumps(flow)
    sanitized_flow_def = nipyapi.utils.dump(flow) #load(json_sanitized_flow)

    # check if the process group exists in the bucket 
    existing_flow = versioning.get_flow_in_bucket(bucket_identifier, flow_name)
    if existing_flow is None:
        # import a new flow into the Registry
        print(F"Importing new flow {flow_name} into registry into {bucket.name}")
        vflow = versioning.import_flow_version(
                                bucket_id=bucket_identifier,
                                encoded_flow=sanitized_flow_def,
                                flow_name=flow_name)
        time.sleep(5)
    
        print(F"Deploying new flow {flow_name} into registry onto the canvas")
        # deploy anew into the Canvas
        versioning.deploy_flow_version(
                parent_id=root_pg,
                location=(0, 0),
                bucket_id=bucket_identifier,
                flow_id=vflow.flow.identifier,
                reg_client_id=test_reg_client.id,
                )
    else:
        print(F"Importing new version of the flow {flow_name} from registry into {bucket.name}")
        # update Flow in Registry in place
        vflow = versioning.import_flow_version(
                bucket_id=bucket_identifier,
                encoded_flow=sanitized_flow_def,
                flow_id=existing_flow.identifier)
        time.sleep(5)
    
        # check if the Canvas already has the Process Group
        pg = nipyapi.canvas.get_process_group(flow_name, greedy=False)
        if pg is None:
            print(F"Flow did not exist on the canvas; uploading {flow_name} from registry onto the canvas")
            # deploy anew into the Canvas
            versioning.deploy_flow_version(
                    parent_id=root_pg,
                    location=(0, 0),
                    bucket_id=bucket_identifier,
                    flow_id=vflow.flow.identifier,
                    reg_client_id=test_reg_client.id,
                    )
        else:
            print(F"Deploying new version of the flow {flow_name} from registry onto the canvas")
            # update Canvas in place
            versioning.update_flow_ver(process_group=pg)