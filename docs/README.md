<div align="center">

<h1> 🐙 OQTOPUS Cloud </h1>

<table>
  <thead>
    <tr>
      <th style="text-align:center"><a href="./README.md">🇺🇸English</a></th>
      <th style="text-align:center"><a href="./README.ja.md">🇯🇵日本語</a></th>
    </tr>
  </thead>
</table>

[![Python CI](https://github.com/oqtopus-team/oqtopus-cloud/actions/workflows/python-ci.yml/badge.svg)](https://github.com/oqtopus-team/oqtopus-cloud/actions/workflows/python-ci.yml) [![TFLint](https://github.com/oqtopus-team/oqtopus-cloud/actions/workflows/tflint.yml/badge.svg)](https://github.com/oqtopus-team/oqtopus-cloud/actions/workflows/tflint.yml) [![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

</div>

## Overview

**O**pen **Q**uantum **T**oolchain for **OP**erators & **US**ers (**OQTOPUS**) is a project that provides the architecture of cloud quantum computers as an open-source software (OSS).
By using it in conjunction with various OSS provided by [@oqtopus-team](https://github.com/oqtopus-team), you can build a cloud quantum computer system.

![OQTOPUS Cloud](./asset/aws_system_architecture_diagram_overview.drawio.png)

## Features

- **Quantum Computing as a Service (QCaaS)**: Provides a cloud quantum computer system.
- **Quantum Task Management**: Manages quantum tasks and their states.
- **Quatntum Device Management**: Manages quantum devices and their states.

## Documentation

### Architecture

- [AWS System Architecture Diagram](./en/architecture/aws_system_architecture_diagram.md)
- [Sequence Diagram](./en/architecture/sequence_diagram.md)
- [Task State Transition Diagram](./en/architecture/task_state_transition_diagram.md)

### Developer Guidelines

- [Development Flow](./en/developer_guidelines/index.md)
- [Setup Development Environment](./en/developer_guidelines/setup.md)
- [OpenAPI Specification-Based Code Generation](./en/developer_guidelines/openapi.md)
- [Backend Implementation](./en/developer_guidelines/backend.md)
- [Terraform Guidelines](./en/developer_guidelines/terraform_guidelines.md)
- [Terraform Modules](./terraform_modules/README.md)
- [DB Schema](./schema/README.md)

### OpenAPI Specifications

- [User API](./oas/user/openapi.yaml)
- [Provider API](./oas/provider/openapi.yaml)

### Operations

- [Initial Setup](./en/operation/setup.md)
- [Deployment](./en/operation/deployment.md)

### Others

- [How to Contribute](./en/CONTRIBUTING.md)
- [Code of Conduct](./en/CODE_OF_CONDUCT.md)
- [Security](./en/SECURITY.md)

## CITATION

If you use OQTOPUS Cloud in your research, please cite the following GitHub repository:

### APA

```apacite
Aso, N., Gokita, S., Kakuko, N., Masumoto, N., Mori, T., Miyanaga, T., Noda, K., Tsukano, S., & Ymaguchi, M. (2024). OQTOPUS-CLOUD (Version 1.0.0) [Computer software]. https://github.com/oqtopus-team/oqtopus-cloud
```

### BibTeX

```bibtex
@software{Aso_OQTOPUS-CLOUD_2024,
author = {Aso, Noriyasu and Gokita, Shun and Kakuko, Norihiro and Masumoto, Naoyuki and Mori, Toshio and Miyanaga, Takafumi and Noda, Kunihiro and Tsukano, Satoyuki and Ymaguchi, Masaomi},
license = {Apache-2.0},
month = sep,
title = {{OQTOPUS-CLOUD}},
url = {https://github.com/oqtopus-team/oqtopus-cloud},
version = {1.0.0},
year = {2024}
}
```

Citation information is also available in the [CITATION](../CITATION.cff) file.

## Contact

You can contact us by creating an issue in this repository,
or you can contact us by email:

- [oqtopus-team[at]googlegroups.com](mailto:oqtopus-team[at]googlegroups.com)

## LICENSE

OQTOPUS Cloud is released under the [Apache License 2.0](../LICENSE).
