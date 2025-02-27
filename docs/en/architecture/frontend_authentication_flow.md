# Authentication Sequence of User Operations

This page shows the sequence diagram of authentication of users.

## User Job-related Requests (Success Case)

This sequence diagram shows the authentication procedure when the user makes a request.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant AG as API Gateway
    participant LA as Lambda Authorizer
    participant C as Cognito
    participant DB as RDS
    participant L as Lambda

    U->>AG: Job-related request
    AG->>LA: Transfer authentication information
    alt Request from Oqtopus-frontend
      LA->>C: Check the user's existence in the Cognito user pool
      C-->>LA: Success response
    else Request from Command-line
      LA->>DB: Check the user's API token
      DB-->>LA: Record found
    end
    LA->>AG: Success response
    AG->>L: Transfer request
    L->>L: Process the request
    L-->>U: Response to the request
```
