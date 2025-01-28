# Quantum Jobs in Detail

## The Definition of Quantum Job

The quantum job in OQTOPUS is a structure consisting of several fields, some of which also include subfields.
In this section, we describe how quantum jobs are structured.

### Job Info

`JobInfo` is a structure that holds data related to the execution of individual quantum jobs and is composed of the following fields

- **`desc`**  
  The quantum job descriptor, detailed below.
- **`transpiled_code`**  
  The transpiled quantum program which is actually executed on a device.
- **`result`**  
  The computation result. For failed jobs, this field is empty.
- **`reason`**  
  The description of failure. For successful jobs, this field is empty.

The job info descriptor is also a structure with fields varying depending on the job type. All job types have a `job_type` field in common, and its value determines the type of quantum job. 

Currently, the following types of jobs are supported. The structure of the job info descriptor for each job type is as follows:

- **Sampling Job**  
    - `job_type`: `sampling`
    - `code`: The quantum program of the job, written in OpenQASM3.

- **Estimation Job**  
    - `job_type`: `estimation`.
    - `code`: The quantum program of the job, written in OpenQASM3.
    - `operators`:  

### Transpiler Info

### Mitigation Info

### Simulator Info
