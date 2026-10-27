## Gamedays

### Overview

Mock DR events are simulated almost every week by the [Ops team](https://app.slack.com/client/E03N1RJJX7C/C04MH2L07JS) for a service and/or combination of services to test our DR processes and improve on them in case of an actual incident.

### Goal

The goal of the Gamedays is to improve our DR processes and document them in a way so that folks who do not have context about the services can as well execute them the same way in case of an actual outage.

### Attend a Gameday

Join the slack channel [#f_gamedays](https://app.slack.com/client/E03N1RJJX7C/C07PV3F6J1W) to follow updates

Additionally, information before every Gameday is announced in [#production-engineering](https://app.slack.com/client/E03N1RJJX7C/C03QC5KNW5N)

### Roles and Responsibilities

| Role              | Responsibility                                   | Key Actions                                                                                                                                                                                                    |
|-------------------|--------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Change Technician | Execute the gameday scenario and technical steps | Plan and execute all technical procedures <br> Monitor system metrics during execution <br> Document timing and measurements <br> Coordinate with other team members <br> Handle rollback procedures if needed |
| Change Reviewer   | Technical validation and oversight               | Review and approve the gameday plan <br> Verify technical accuracy of procedures <br> Assess risk and rollback strategies <br> Provide technical guidance during execution                                     |

Alternates: Other [on-call engineers](https://handbook.gitlab.com/handbook/engineering/on-call/) in various regions according to their on-call status.

The Networking and Incident Management team should be notified if the procedure fails.

### RTO/RPO

View our current Regional/Zonal RTO [here](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/disaster_recovery/#current-recovery-time-objective-rto-and-recovery-point-objective-rpo-for-zonal-recovery)

#### Definitions

#### Confidence Levels

We have clear confidence levels setup for each of the services that helps represent how efficient our current DR process is.

#### Zonal Confidence Level

- <b>No confidence</b>
    1. We have not tested recovery
    2. We do not have a good understanding of the impact of the component going down
    3. We do not have an emergency plan for when the component goes down

- <b>Low confidence</b>
    1. We have not tested recovery
    2. We have a good understanding of the impact of the component going down
    3. We may or may not have an emergency plan when the component goes down, but it has not been validated

- <b>Medium confidence</b>
    1. We have tested recovery in a production like environment but not tested in production
    2. We have a good understanding of the impact of the component going down
    3. We have an emergency plan for when the component goes down, and it has been validated in some environment

- <b>High confidence</b>
    1. We have tested recovery in production
    2. We have a good understanding of the impact of the component going down
    3. We have an emergency plan when the component goes down, and it has been validated

<b>View our Zonal Confidence levels [here](https://docs.google.com/spreadsheets/d/16AVXetqTae2eTarJIg9CGJkvRrsz3Fh9RdFZ-0b48nY/edit?gid=0#gid=0)</b>

### Regional Confidence Level

- <b>No Confidence</b>
    1. We do not have an emergency plan in place
    2. We do not have confidence that a service can be recreated in a new region

- <b>Low Confidence</b>
    1. We have ensured data is replicated and accessible in another region.
    2. We do not have an emergency plan* in place

- <b>Medium Confidence</b>
    1. We have ensured data is replicated
    2. We have plans* to build infrastructure in place

- <b>High Confidence</b>
    1. We have automated testing for data that is replicated
    2. We have infrastructure ready to recieve traffic"

*Note* : The plan mentioned in the Regional Confidence includes expanding Terraform to facilitate other region resources.

<b>View our Regional RTO [here](https://docs.google.com/spreadsheets/d/16AVXetqTae2eTarJIg9CGJkvRrsz3Fh9RdFZ-0b48nY/edit?gid=983753226#gid=983753226)</b>

#### Phases

Phases are groupings that show what can be done in parallel. Items in the same phase can be done at the same time.

### Time Measurements

During the process of testing our recovery processes for Zonal and Regional outages, we want to record timing information.
There are three different timing categories right now:

1. Fleet specific VM recreation time
2. Component specific DR restore process time
3. Total DR restore process time

#### Common measurements

<b>VM Provision Time</b>
This is the time from when an apply is performed from an MR to create new VMs until we record a successful bootstrap script completion.
In the bootstrap logs (or console output), look for Bootstrap finished in X minutes and Y seconds.
When many VMs are provisioned, we should find the last VM to complete as our measurement.

<b>Bootstrap Time</b>
During the provisioning process, when a new VM is created, it executes a bootstrap script that may restart the VM.
This measurement might take place over multiple boots.
This script can help measure the bootstrap time.
This can be collected for all VMs during a gameday, or a random VM if we are creating many VMs.

<b>Gameday DR Process Time</b>
The time it takes to execute a DR process. This should include creating MRs, communications, execution, and verification.
This measurement is a rough measurement right now since current process has MRs created in advance of the gameday.
Ideally, this measurement is designed to inform the overall flow and duration of recovery work for planning purposes.

**Note** : View time measurements [here](recovery-measurements.md)
