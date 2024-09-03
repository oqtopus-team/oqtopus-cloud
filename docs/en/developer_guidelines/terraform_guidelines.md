
# Terraform Guidelines

## Style Guide

The official style guide is provided by Terraform. As a rule, please adhere to the following document:

[Style Guide - Configuration Language | Terraform | HashiCorp Developer](https://developer.hashicorp.com/terraform/language/style)

## Naming Conventions for AWS Resources

Please follow the guidelines below for naming AWS resources.

### Components of the Name

- {product}: Product name (e.g., oqtopus)
- {org}: Organization name (e.g., example)
- {env}: Environment name (e.g., dev, stg, prd)
- {identifier}: Identifier (e.g., user, provider)

### Principles

Unless there is an exception, resource names should follow the format below:

```bash
{product}-{org}-{env}-{identifier}-{name}
```

For example, in the case of a Lambda function for the USER API, it would look like this:

```bash
oqtopus-example-user-api
```

## References

- [Future Enterprise Naming Convention Standards for AWS infrastructure resource](https://future-architect.github.io/coding-standards/documents/forAWSResource/AWS%E3%82%A4%E3%83%B3%E3%83%95%E3%83%A9%E3%83%AA%E3%82%BD%E3%83%BC%E3%82%B9%E5%91%BD%E5%90%8D%E8%A6%8F%E7%B4%84.html)
