# juptyerhub-placeholder-scaler

Draft of a service to autoscale jupyterhub placeholders

keeps placeholder replica count updated to meet:

- minimum placeholder count
- minimum total capacity (current users + placeholder count)

Reflectors are vendored from kubespawner 0.15. If this code ran in the Hub pod, they could just be imported.

[For @yuvipanda](https://discourse.jupyter.org/t/request-for-implementation-jupyterhub-aware-kubernetes-cluster-autoscaler/7669)

Idea from [@manics and @betatim](https://discourse.jupyter.org/t/request-for-implementation-jupyterhub-aware-kubernetes-cluster-autoscaler/7669/7)

Event descriptions are searched for lines that look like:

```
min_placeholders: 10
min_capacity: 100
```

Only `min_capacity` and `min_placeholders` assignments are used, and only integer values are applied.

## Configuration

The following environment variables configure the behavior:

- NAMESPACE - the kubernetes namespace in which to look for pods
- PLACEHOLDER_MIN_COUNT - the minimum number of placeholders to have in place, when not overridden by a calendar event
- PLACEHOLDER_MIN_CAPACITY - the minimum total "warm" capacity,
  taking current active users into account, when not overridden by a calendar event
- PLACEHOLDER_CHECK_INTERVAL - the interval, in seconds,
  on which to check and update the placeholder count.
  The calendar, if defined, is fetch each time.
- PLACEHOLDER_ICS_URL - URL for a .ics-format calendar (e.g. a public google calendar link)


## Test your calendar

You can test your calendar and see what the placeholder counts will be over time with:

    python -m placeholderscaler.plan $calendar_url

which will show you each change in the placeholder count due to calendar events.
