# Disaster Recovery Gameday Schedule

The following is the schedule for gamedays in FY26 and FY27. We're assigning these in a round-robin style, so the schedule continues until every team has had an opportunity to do each Gameday. The teams are free to schedule the gameday at their convenience, but they must be completed by the end of the quarter.

## Gameday Kinds

We currently have 4 different types of gameday.

1. [Gitaly](recovery-measurements.md#gitaly)
2. [Patroni/pgbouncer](recovery-measurements.md#patronipgbouncer)
3. [HAProxy/Traffic Routing](recovery-measurements.md#haproxytraffic-routing-zonal-outage-dr-process-time)
4. [CI Runners](recovery-measurements.md#ci-runner-zonal-outage-dr-process-time)

## Included Teams

The following teams have been identified as necessary to perform gamedays and be familiar with our Disaster Recovery processes.

- [Networking & Incident Management](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production-engineering/networking-and-incident-management/)
- [Durability](https://handbook.gitlab.com/handbook/engineering/data-engineering/database-excellence/)
- [Observability](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production-engineering/observability/)
- [DB Operations](https://handbook.gitlab.com/handbook/engineering/data-engineering/database-excellence/database-operations/)
- [Runway](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/gitlab-delivery/runway/)
- [Delivery](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/gitlab-delivery/delivery/)
- [Runners Platform](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production-engineering/runners-platform/)

## FY26-Q1

| Gameday           | Team          |
| ----------------- | ------------- |
| HAproxy           | Foundations   |
| pgbouncer/patroni | Durability    |
| Gitaly            | Observability |
| CI Runners        | DB Operations |

## FY26-Q2

| Gameday           | Team                  |
| ----------------- | --------------------- |
| ~~HAproxy~~       | ~~Runway~~            |
| pgbouncer/patroni | Delivery: Release     |
| Gitaly            | Delivery: Deployments |
| CI Runners        | Foundations           |

## FY26-Q3

| Gameday           | Team          |
| ----------------- | ------------- |
| HAproxy           | Durability    |
| pgbouncer/patroni | Observability |
| Gitaly            | DB Operations |
| CI Runners        | Runway        |

## FY26-Q4

| Gameday | Team |
| ------ | ------ |
| HAproxy | Delivery |
| pgbouncer/patroni | Durability |
| Gitaly | Networking & Incident Management |
| CI Runners | Runners Platform |

## FY27-Q1

| Gameday | Team |
| ------ | ------ |
| HAproxy | Runway |
| pgbouncer/patroni | Delivery |
| Gitaly | Runners Platform |
| CI Runners | Networking & Incident Management |

## FY27-Q2

| Gameday | Team |
| ------ | ------ |
| HAproxy | Durability |
| pgbouncer/patroni | Observability |
| Gitaly | DBO |
| CI Runners | Runway |

## FY27-Q3

| Gameday | Team |
| ------ | ------ |
| HAproxy | Delivery |
| pgbouncer/patroni | Runners Platform |
| Gitaly | Networking & Incident Management |
| CI Runners | Durability |

## FY27-Q4

| Gameday | Team |
| ------ | ------ |
| HAproxy | Observability |
| pgbouncer/patroni | DBO |
| Gitaly | Runway |
| CI Runners | Delivery |

## FY28-Q1

| Gameday | Team |
| ------ | ------ |
| HAproxy | Runners Platform |
| pgbouncer/patroni | Networking & Incident Management |
| Gitaly | Durability |
| CI Runners | Observability |
