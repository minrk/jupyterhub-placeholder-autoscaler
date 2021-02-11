# juptyerhub-placeholder-scaler

Draft of a service to autoscale jupyterhub placeholders

keeps placeholder replica count updated to meet:

- minimum placeholder count
- minimum total capacity (current users + placeholder count)

Reflectors are vendored from kubespawner 0.15. If this code ran in the Hub pod, they could just be imported.

[For @yuvipanda](https://discourse.jupyter.org/t/request-for-implementation-jupyterhub-aware-kubernetes-cluster-autoscaler/7669)

Idea from [@manics and @betatim](https://discourse.jupyter.org/t/request-for-implementation-jupyterhub-aware-kubernetes-cluster-autoscaler/7669/7)
