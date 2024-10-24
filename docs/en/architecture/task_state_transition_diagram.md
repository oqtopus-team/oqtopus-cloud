# Task State Transition

The time to stay in the RUNNING state can be very short, so it can be skipped.
For example, QUEUED state tasks can be transitioned to COMPLETED directly.

```mermaid
stateDiagram-v2
  [*] --> QUEUED :task submitted

  QUEUED --> RUNNING :execution started
  
  state join_state <<join>>
  RUNNING --> join_state
  
  state join_state <<fork>>
  join_state --> COMPLETED :execution succeeded
  join_state --> FAILED :execution failed
  join_state --> CANCELLING :cancel requested
  
  COMPLETED --> [*] :deleted
  FAILED --> [*] :deleted
  CANCELLING --> CANCELLED :cancelled in a gateway
  QUEUED --> CANCELLED :cancelled requested (cancelled in the cloud PF)
  CANCELLED --> [*] :deleted
```
