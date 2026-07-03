import random

import pytest
from opentelemetry.sdk.trace.id_generator import RandomIdGenerator

from oqtopus_cloud.common import tracing


@pytest.fixture(autouse=True)
def restore_random_state():
    state = random.getstate()
    yield
    random.setstate(state)


def _trace_ids_from_restored_env(snapshot, reseed):
    # Emulate a SnapStart restore: every restored environment starts from the
    # same PRNG state that was frozen into the snapshot at Init time.
    random.setstate(snapshot)
    if reseed:
        tracing._reseed_random_after_snapstart()
    generator = RandomIdGenerator()
    return [generator.generate_trace_id() for _ in range(2)]


def test_restored_environments_collide_without_reseed():
    # Documents the hazard: without the hook, two environments restored from the
    # same snapshot generate identical trace-id sequences.
    snapshot = random.getstate()
    first = _trace_ids_from_restored_env(snapshot, reseed=False)
    second = _trace_ids_from_restored_env(snapshot, reseed=False)
    assert first == second


def test_reseed_diverges_trace_ids_across_restored_environments():
    snapshot = random.getstate()
    first = _trace_ids_from_restored_env(snapshot, reseed=True)
    second = _trace_ids_from_restored_env(snapshot, reseed=True)
    assert first != second


def test_register_hook_is_noop_when_runtime_module_absent():
    # snapshot_restore_py ships only with the AWS Lambda managed runtime, so the
    # registration must degrade to a no-op locally rather than raise.
    tracing._register_snapstart_restore_hook()
