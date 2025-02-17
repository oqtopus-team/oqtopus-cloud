# Job State Transition

A job can have the following states.

- **`submitted`**
  The state when the user has submitted a job to OQTOPUS Cloud.
- **`ready`**
  The state when the backend retrieves the job via the OQTOPUS Cloud Provider API.
  At this stage, the backend holds the job, but it has not yet been executed on a QPU or simulator.
- **`running`**
  The state when the job is being executed on a QPU or simulator.
- **`succeeded`**
  The state when the job has completed successfully.
- **`failed`**
  The state when the job has failed due to an error.
- **`cancelled`**
  The state when the job execution has been canceled.

The following diagram shows the job state transitions.

```mermaid
stateDiagram-v2
    [*] --> submitted :job submitted

    submitted --> ready : job readying
    ready --> running : execution started

    state join_state <<join>>
    running --> join_state

    state join_state <<fork>>
    join_state --> succeeded :execution succeeded
    join_state --> failed :execution failed
    join_state --> cancelled :cancel requested

    succeeded --> [*] :deleted
    failed --> [*] :deleted
    submitted --> cancelled :cancel requested (cancelled in the cloud PF)
    ready --> cancelled :cancel requested
    cancelled --> [*] :deleted
```
