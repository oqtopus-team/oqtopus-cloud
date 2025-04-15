# Sign-up and Sign-in Sequence Diagrams

This page shows a sequence diagram of user sign-up, sign-in, MFA reset, and password reset procedures.

## User Sign-up Sequence (Success case)

The following sequence diagram shows successful user registration: the API Gateway and Lambda function are between the user and Cognito user pool, ensuring the user is whitelisted.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant AG as API Gateway
    participant L as Lambda
    participant C as Cognito
    participant DB as RDS

    U->>AG: Signup request
    AG->>L: Forward request
    L->>DB: Check the Email listed in whitelist
    DB-->>L: Record
    L->>C: Email confirmation request
    L->>DB: Register new user
    C-->>U: Email confirmation code (Email sent)
    U->>AG: Email confirmation request (code input)
    AG->>L: Forward request
    L->>C: Validate confirmation code
    C-->>L: Success response
    L->>C: MFA code publish request (AssociateSoftwareToken)
    C-->>U: MFA secret value (otpauth URL/secret)
    U->>C: MFA code confirm (VerifySoftwareToken)
    C-->>U: Session
```

## User Sign-up Sequence (Email not in whitelist failure case)

The following sequence diagram shows the case where the user is not listed in the whitelist.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant AG as API Gateway
    participant L as Lambda
    participant C as Cognito
    participant DB as RDS

    U->>AG: Signup request
    AG->>L: Forward request
    L->>DB: Check the Email listed in whitelist
    DB-->>L: No Record
    L-->>U: Error response
```

## User Sign-up Sequence (Email confirmation failure case)

The following sequence diagram shows the the case where the user failed to validate the confirmation code.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant AG as API Gateway
    participant L as Lambda
    participant C as Cognito
    participant DB as RDS

    U->>AG: Signup request
    AG->>L: Forward request
    L->>DB: Check the Email listed in whitelist
    DB-->>L: Record
    L->>C: Email confirmation request
    L->>DB: Register new user
    C-->>U: Email confirmation code (Email sent)
    U->>AG: Email confirmation request (code input)
    AG->>L: Forward request
    L->>C: Validate confirmation code
    C-->>L: Error response
    L->>C: Rollback user registration (delete the Cognito user)
    L->>DB: Rollback user registration (delete the user record)
    L-->>U: Error response
```

## User Sign-in Sequence

The brief sequence diagram shows the sign-in procedure. No intermidiate service like API Gateway and Lambda exists.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant C as Cognito

    U->>C: Sign-in request (Send Email and password)
    C-->>U: Session
```

## User MFA Reset Sequence

The following sequence diagram shows the MFA reset procedure. The user can reset the MFA device anytime if the Email and the password match.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant AG as API Gateway
    participant L as Lambda
    participant C as Cognito

    U->>AG: MFA reset request (Email and password)
    AG->>L: Forward request
    L->>C: Check User registration
    C-->>L: Success response
    L->>C: MFA reset
    C-->>L: Success response
    L-->>U: Success response
```

## Sequence of Password Reset

The following sequence diagram shows a user resetting a password.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant C as Cognito

    U->>C: ForgotPassword API (Send Email)
    C-->>U: Confirmation code
    U->>C: Send confirmation code and new password
    C-->>U: Success response
```
