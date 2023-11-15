import nipyapi
from collections import namedtuple
from nipyapi.registry.models.versioned_flow_snapshot import VersionedFlowSnapshot
from nipyapi.registry.models.versioned_process_group import VersionedProcessGroup
from nipyapi.registry.models.versioned_parameter_context import VersionedParameterContext
from nipyapi.registry.models.versioned_parameter import VersionedParameter
import json
import time

def create_or_update_parameter_context(name: str, ctx: VersionedParameterContext):
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
    print(param)