# Incident Workflow

Here are some quick reference diagrams for what each role should be doing during an incident.

## Engineer on Call (EOC)

```mermaid
flowchart TD
    start([Alert/Incident Reported]) --> acknowledge[Acknowledge alert in PagerDuty within 15 minutes]
    acknowledge --> check[Check #incidents-dotcom-triage for triage incident]
    check --> ongoing[Ongoing incident?]
    ongoing --> |Yes| merge[Merge into other incident]
    ongoing --> |No| accept[Accept incident]
    accept --> evaluate{Evaluate severity}
    evaluate --> lead[Are you incident Lead?]
    lead --> |Yes| setLead[Set yourself with /incident lead]
    lead --> |No| otherLead[Determine who is]
    setLead --> update[Provide regular updates via /inc update]
    otherLead --> investigate
    update --> investigate
    investigate --> mitigate[Migitage Incident]
    mitigate --> resolved{Incident resolved?}
    resolved --> |Yes| document[Document incident, complete Incident Summary]
    resolved --> |No| investigate
    document --> review[Review for corrective actions]
    review --> completed([Incident Complete])
```

## Incident Manager (IMOC)

## Communications Manager (CMOC)
