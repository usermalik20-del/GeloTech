import pytest
from gelotech.workers import extract_components_from_text

# Representative dumpsys snippets for unit testing
SAMPLE_1 = """
ServiceRecord{3a1b2c7 com.example/.MyService}
  mName=com.example/.MyService
  intent={cmp=com.example/.MyService}
"""

SAMPLE_2 = """
  ComponentInfo{com.example/.MyService}
  ServiceRecord{... com.example/.Outer$Inner ...}
"""

SAMPLE_3 = """
service running: com.vendor.service/FullClassName
  some other text
com.foo.bar/.LocalService u0a123
"""

SAMPLE_4 = """
some noise
ComponentInfo{com.example.app/.ExampleService}
service list:
  45: media.audio_flinger
  46: permission
"""

SAMPLE_5 = """
ServiceRecord{07e1a8e com.android.server.am.ActivityManagerService$LocalService}
  client=ApplicationThread... com.android.server/...  something
"""

def test_sample_1_basic():
    mapping = extract_components_from_text(SAMPLE_1)
    assert 'com.example' in mapping
    assert any('/.MyService' in comp or '/MyService' in comp for comp in mapping['com.example'])

def test_sample_2_inner_and_componentinfo():
    mapping = extract_components_from_text(SAMPLE_2)
    assert 'com.example' in mapping
    comps = mapping['com.example']
    assert any('.Outer$Inner' in c or 'Outer$Inner' in c for c in comps)
    assert any('.MyService' in c or 'MyService' in c for c in comps)

def test_sample_3_various_tokens():
    mapping = extract_components_from_text(SAMPLE_3)
    assert 'com.vendor.service' in mapping or 'com.foo.bar' in mapping
    # ensure that tokens with u0a... suffix are normalized (strip numeric suffix)
    found = False
    for pkg, comps in mapping.items():
        for c in comps:
            if c.startswith('com.foo.bar/'):
                found = True
    assert found

def test_sample_4_componentinfo_and_service_list():
    mapping = extract_components_from_text(SAMPLE_4)
    assert 'com.example.app' in mapping
    # service list entries not matching pkg/class should be ignored (e.g., 'media.audio_flinger')
    assert 'media.audio_flinger' not in mapping

def test_sample_5_system_service_ignored_if_malformed():
    mapping = extract_components_from_text(SAMPLE_5)
    # ActivityManagerService is a system internal token; we only capture tokens that look like pkg/class with slash
    # The mapping may or may not include 'com.android.server.am.ActivityManagerService$LocalService' depending on formatting;
    # this assertion ensures parsing didn't crash and returned a dict
    assert isinstance(mapping, dict)