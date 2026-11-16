# Deploy a Fabric workspace with pyfabricops

A template repository: the script and the pipelines that deploy the items of
a Fabric workspace, with [pyfabricops](https://github.com/alisonpezzott/pyfabricops),
to one workspace per environment. Each environment is a YAML file that
names its workspace and the branch that deploys to it: by default, `dev`
from `develop` and `prod` from `main`. Make a repository from it, fill in
the environment files, and put the items in `fabric-workspace/`.

The repository can be written in two ways, and the script tells them apart
by the environment files:

- **dev connected to Git** (the default of this template). Fabric Git
  integration syncs the dev workspace with `fabric-workspace/`. A run of
  `develop` only updates dev from Git; no item is deployed to it through
  the API. The items hold the IDs of dev, so for prod the script maps each
  dev ID to the ID of the same item in prod before sending it. Every item
  type pyfabricops deploys can go this way.
- **No workspace connected to Git.** Power BI Desktop saves a Power BI
  Project, which holds no workspace IDs, and the repository is the source of
  every environment, dev included. Only variable libraries, semantic models
  and reports go this way.

Either way, a workspace may be on a Fabric capacity or a Pro workspace,
without one, and the environments may mix them. Nothing records what a run
deployed: each run compares the repository with the workspace and sends
what differs.

```text
.
├── fabric-workspace/                 the items: Git folder of dev, or a Power BI Project
├── environments/dev.yml              dev: its workspace and branch, connected to Git
├── environments/prod.yml             prod: its workspace, branch, value set and connections
├── scripts/deploy.py                 deploys, plans, reconciles; updates dev from Git
├── scripts/environments.py           reads environments/, tells the environment of a branch
├── azure-pipelines/deploy.yml        Azure DevOps: runs when a branch of an environment changes
├── .github/workflows/deploy.yml      GitHub Actions: runs when a branch of an environment changes
└── .env.example                      the credentials, for local runs
```

| Environment | File | Branch | Who writes the workspace |
| :--- | :--- | :--- | :--- |
| `dev` | `environments/dev.yml` | `develop` | Fabric Git integration, updated from Git by the pipeline |
| `prod` | `environments/prod.yml` | `main` | `scripts/deploy.py` |

## Set up a new repository

1. **Make the repository.**
   - On GitHub: **Use this template** > **Create a new repository**, then
     create `develop` from `main`.
   - On Azure DevOps: **Repos** > **Import repository**, with the clone URL
     of this repository, then create `develop` from `main`. Importing a
     private repository asks for a personal access token with read access
     to it.
2. **Fill in the environment files.** Replace `workspace-name-or-id-dev` and
   `workspace-name-or-id-prod` with the name or ID of each workspace. Keep
   `gitConnected: true` in `dev.yml`. In `prod.yml`, keep `valueSet` only
   if the workspace will have a variable library with a value set of that
   exact name; otherwise remove it (see [The environments](#the-environments)).
3. **Connect dev to Git** (Workspace settings > Git integration) on
   `develop`, with `fabric-workspace` as the Git folder.
4. **Commit the items of dev** from **Source control** in the workspace.
   Fabric writes one folder per item into `fabric-workspace/`.
5. **Give the service principal Git credentials on dev**, so that a run
   of `develop` can update it from Git (see
   [The environment connected to Git](#the-environment-connected-to-git)).
6. **Prepare the credentials and connections** listed in
   [Before you start](#before-you-start).
7. **Create the pipeline** of [Deploy from CI](#deploy-from-ci).
8. **Check the first deployment** before running it:
   `python scripts/deploy.py --environment prod --plan`.

`fabric-workspace/README.md` only keeps the folder in Git while it has no
items. Fabric Git integration ignores it, and so does the script.

## What can go in `fabric-workspace/`

| dev connected to Git | No workspace connected |
| :--- | :--- |
| Every item type pyfabricops deploys, such as lakehouses, warehouses, mirrored databases, eventhouses and their KQL databases, notebooks, pipelines, Direct Lake models, variable libraries, semantic models, reports, eventstreams, ontologies and data agents | Variable libraries, import or DirectQuery semantic models, and reports |

An item of a type pyfabricops does not deploy, such as a type newer than
the pyfabricops of the pipeline, is not deployed: make it by hand in each
workspace, with the same name. The run sends nothing of it, but what refers
to it goes pointed at the one of the target. `--reconcile` does not count
it as unmanaged, and no run deletes it.

The script stops before it deploys anything when the repository has:

- an item of a type pyfabricops does not deploy that the target workspace
  lacks;
- without an environment connected to Git, any item but a variable library,
  a semantic model or a report, or a Direct Lake model: their IDs would
  still point to dev;
- for a Pro workspace, any item but a semantic model or a report;
- a model saved as `model.bim`: the script reads the parameters of TMDL
  only.

### Mirrored databases

A mirrored database is deployed before the lakehouses, whose shortcuts may
point to its tables, and each environment needs a source of its own: a
source database feeds one mirrored database only, so prod mirrors another
database, on another server or under another name. `connections` in the
file of the environment gives the connection to it in place of the one of
dev (see [The environments](#the-environments)); the run says when a
mirrored database is left on the connection of dev, or when the connection
of the environment reaches the same server and database as the one of dev.

Its replication is not part of its definition: each run checks that it
runs, starts it when it does not, and waits for it before deploying the
lakehouses. `--reconcile` checks that it runs. What no Fabric API does,
before the first deployment to an environment, at its source:

- the identity of its connection, such as the service principal, needs a
  user in the source database with `SELECT`, `ALTER ANY EXTERNAL MIRROR`,
  `VIEW DATABASE PERFORMANCE STATE` and `VIEW DATABASE SECURITY STATE`;
- for Azure SQL Database, the system-assigned managed identity of the
  logical server must be on.

Check the Fabric documentation on mirroring for the source in use: its
prerequisites change. When the replication cannot start, the run fails and
points at the error shown on the mirrored database in Fabric, such as a
rejected secret of its connection, a source already mirrored elsewhere or a
missing permission.

## How you work

1. Work in the dev workspace, or in Power BI Desktop against dev.
2. Commit from **Source control** in the dev workspace to `develop`, or
   from a feature branch through a pull request to `develop`. The pipeline
   then updates dev from Git, so that what reached `develop` from outside
   the workspace, such as a merged pull request, gets there too.
3. Open a pull request from `develop` to `main`. Once it is merged, the
   pipeline deploys to prod.

Never edit or publish to prod by hand: the next deployment overwrites it.
`python scripts/deploy.py --environment prod --reconcile` tells, at any
time, whether prod still matches `main`.

## The environments

Everything that tells dev from prod is in `environments/<env>.yml`, in Git
and reviewed in pull requests like the items. One file per environment, so
that a change to prod is a change to `prod.yml` alone, and a `CODEOWNERS`
entry on it can ask the right people to review it. The file name is the
environment name: the one passed to `--environment`, and the name of the
environment in GitHub or Azure DevOps. Use lowercase letters, digits and
`-`. The files are YAML, so they hold comments too.

The pipeline names no environment: it passes its branch, and the file
whose `branch` matches says where it deploys.

The environment connected to Git gives its workspace and its branch, and
nothing else. At most one environment may be connected:

```yaml
workspace: workspace-name-or-id-dev
branch: develop
gitConnected: true
```

Every other environment gives its workspace, its branch and, optionally,
the value set of its variable libraries, the parameters of its semantic
models, the connections that replace those of dev and the orphans to keep:

```yaml
workspace: workspace-name-or-id-prod
branch: main
valueSet: Production
parameters:
  <model name>:
    <parameter name>: "<value in prod>"
connections:
  <connection of dev>: <connection of prod>
keep:
  - "Sandbox .*"
```

| Key | What it does |
| :--- | :--- |
| `workspace` | The workspace to deploy to, by name or ID. `--workspace` overrides it for a local run. |
| `branch` | The branch that deploys to it, by name or as a glob such as `release/*`. No branch may deploy to two environments. Without it, the environment is deployed only with `--environment`. |
| `gitConnected` | `true` for the environment Fabric Git integration writes. No item is deployed to it through the API: a run of its branch updates it from Git, and the runs of the other environments read its items to translate their IDs. |
| `valueSet` | The value set made active in every variable library after the deployment. Every library must have it, with this exact name, and the run stops when the repository has no variable library. Without it, the libraries keep their default values, which are those of dev. |
| `parameters` | The text parameters of each semantic model, by model and parameter name. Quote every value, and any name YAML could read otherwise: YAML reads `5432` as a number and `yes` or `on` as true, and the run stops on a name or a value that is not text. A parameter left out keeps the value of the repository, the one of dev, and the run says which; so does a parameter that is not text, such as a date, which the file cannot set. A model or parameter the repository does not have stops the run, so a misspelled name never goes unnoticed. |
| `connections` | The connection of this environment in place of each connection of dev, both by name or by ID; the ID of the one of dev is in the items, such as `mirroring.json` of a mirrored database. Every ID of the one of dev in the items becomes the ID of the other, as the source of a mirrored database, the connection of a shortcut or of a copy activity. A mirrored database also gets the database its new connection names. The service principal must be a user of both: a name it cannot see stops the run, and an ID it cannot see leaves the database of a mirrored database as it is, which the run says. Prefer names. |
| `keep` | The names of the items `--allow-deletions` leaves in the workspace although the repository does not have them, as regular expressions matched against the whole display name, such as `"Sandbox .*"`. Escape `.`, `(` and the other special characters of a literal name. |

Whether the workspace is on a capacity is not in the file: the script reads
it from Fabric.

To add an environment, such as `test` from `release/*`, add
`environments/test.yml` with `branch: release/*`, and the environment
`test` in GitHub or Azure DevOps. GitHub Actions needs nothing else; in
Azure DevOps, add `test` to the `environments` parameter of
`azure-pipelines/deploy.yml`, which must know its environments before it
reads any file.

## The environment connected to Git

Fabric Git integration does not bring into the workspace what reaches its
branch from elsewhere, such as a pull request merged into `develop` or a
push from a laptop, until someone selects **Update** in **Source control**.
A run of `develop` does that instead, through the Git API of Fabric, and
deploys no item through the item API:

- a workspace already on the commit of `develop` is left alone, as after a
  commit made from the workspace itself, which also triggers the pipeline;
- a workspace with changes not committed yet is not updated, as the update
  would discard them: the run fails and names them, to be committed or
  undone in **Source control**;
- otherwise it is updated to the commit of `develop`, and the run waits.
  When the commits since touch no item, such as a change to the scripts,
  the update only moves the workspace to the commit.

`--plan` tells what an update would bring; `--reconcile` fails when the
workspace is not on the commit of its branch, or has changes not committed.

### Git credentials of the service principal

The service principal calls the Git API as itself, so it needs Git
credentials of its own on the dev workspace. Being a user of a source
control connection is not enough: its credentials must point at it. Set it
up once:

1. Create a source control connection to the repository in **Manage
   connections and gateways**: for GitHub, of type GitHub with a
   fine-grained token that can read and write the contents of the
   repository; for Azure DevOps, of type Azure DevOps source control.
   Make the service principal a user of it.
2. As the service principal, with the `.env` of [Run it](#run-it), point
   its Git credentials on the dev workspace at that connection:

   ```python
   import pyfabricops as pf
   from dotenv import load_dotenv

   load_dotenv()
   pf.set_auth_provider("env")
   pf.update_my_git_connection(
       "<dev workspace>",
       request_body_type="UpdateGitCredentialsToConfiguredConnectionRequest",
       connection_id="<connection id>",
   )
   ```

Until then, a run of `develop` fails with `GitCredentialsNotConfigured` and
a pointer here. The setting belongs to one service principal on one
workspace, and Fabric keeps it. Set it up again when:

- a repository made from this template has a dev workspace of its own;
- the pipeline uses another service principal;
- the workspace is disconnected from Git and connected again;
- the source control connection is deleted.

When the token of the connection expires, the runs of `develop` fail
reading the Git status again: renew the token in the connection, and leave
the credentials of the service principal as they are. The connection types
that hold Git credentials for a service principal change with Fabric:
check the Fabric documentation on Git integration with service principals
before the first setup.

## What a deployment does

For the environment of the branch, `scripts/deploy.py`:

1. When the environment is connected to Git, updates it from Git and
   stops there (see
   [The environment connected to Git](#the-environment-connected-to-git)).
2. Copies `fabric-workspace/` to a staging folder, without what Git ignores
   (the data cache and local settings of `.pbi`) and without
   `diagramLayout.json`, which the service does not keep. The repository is
   never changed.
3. Stops when the staging copy has what it cannot deploy (see
   [What can go in `fabric-workspace/`](#what-can-go-in-fabric-workspace)),
   and checks the environment file: its parameters and its value set.
4. Sets the text parameters of each model in the staging copy, and puts
   the connections of `connections` in place of those of dev.
5. With dev connected to Git, maps each ID of dev in the staging copy to the
   ID of the same item, by type and name, in the target workspace. Fabric
   lists both workspaces at every run. This covers, for example, the
   default lakehouse of a notebook, the OneLake source of a Direct Lake
   model and the items a pipeline runs. A shortcut to a lakehouse of the
   same workspace gets the logical ID of that lakehouse in the target; a
   shortcut to any other item, such as the tables of a mirrored database,
   gets the ID of the item and of the target workspace, as Fabric resolves
   no other logical ID in a shortcut. The query URI of each eventhouse and
   the SQL endpoint of dev become those of the target as well.
6. Reconciles the staging copy with the workspace: reads the definition of
   every item found on both sides, once, and compares them, leaving out
   what Fabric rewrites by itself. The workspace is the deployment state,
   so nothing else records what a run sent.
7. Sends only the items the workspace lacks or that differ from the
   repository, whether Git changed them or someone changed them in the
   workspace; a model whose parameters there differ is one of them. An
   item whose definition Fabric does not return cannot be compared, so
   every item of its type is sent. A run that failed leaves nothing to
   resume: the next one sends what still differs.
8. Sends them one item type at a time, in the dependency order of
   pyfabricops, with pipelines last, without reading their definitions
   again. An item then refers by ID only to items already in the target,
   and a report bound to its model by path goes bound to the ID of the
   model there. Within a type, the items the others refer to go first,
   such as a lakehouse a shortcut points to. The run stops before it sends
   an item that would still refer to dev.
9. Makes the value set of the environment active in each variable library,
   and reads it back. The active value set is not part of the definition, so
   no deployment sets it otherwise. Likewise, once the mirrored databases
   are deployed, checks that each one replicates, starts it when it does
   not, and waits for it, before the lakehouses.
10. With `--allow-deletions`, deletes the orphans: the items of the types
    the run manages that the workspace holds and the repository does not.
    See [Deletions](#deletions).
11. For each import model deployed, never refreshed, or whose last
    refresh failed: the service principal takes the model over; each SQL
    data source is bound to the **shareable cloud connection** of the same
    `server;database`; and the model is refreshed and the run waits for it.
    The refresh is a plain one, without the options of an enhanced refresh,
    which a workspace without a capacity refuses. A Direct Lake model is
    left alone: it reads its tables as they are loaded.
12. Publishes each data agent it deployed: its users get only what is
    published.

The run fails when any step fails, and the next run retries a model that was
deployed but neither bound nor refreshed.

## Deletions

An orphan is an item the workspace holds and the repository does not, of a
type the run manages. Nothing tells whether it was deleted in Git or created
in the workspace by hand, so every run lists the orphans, and only a run
with `--allow-deletions` deletes them, once every other item is deployed and
in the reverse of the deployment order, so that a report goes before its
model. `--plan` lists what it would delete.

Some orphans are never deleted, with or without the option:

- **Items that hold data:** lakehouses, warehouses, mirrored databases,
  eventhouses and KQL databases. Delete them by hand.
- **Items whose name matches `keep`** in the file of the environment.
- **Items of a type the run does not manage**, such as a dashboard, or
  without dev connected to Git, any item but a variable library, a semantic
  model or a report.

A semantic model or a report deleted this way is gone for good; Fabric keeps
other types in the workspace recycle bin. The pipeline does not pass
`--allow-deletions`: add it once the repository holds every item the
workspace should have.

## Before you start

- **pyfabricops 0.12.0 or later, and PyYAML 6.** The pipeline installs
  `pyfabricops>=0.12.0,<0.13.0`: before 1.0, a new minor version may change
  behavior, so move to one on purpose.
- **A service principal**, allowed to call the Fabric and Power BI APIs by
  the tenant settings, Contributor of each workspace it deploys to, able to
  read the items of dev when dev is connected to Git, and with Git
  credentials of its own on dev (see
  [Git credentials of the service principal](#git-credentials-of-the-service-principal)).
- **A shareable cloud connection per environment** to each SQL server and
  database an import model reads, with the service principal as a user of
  it. The script finds it by server and database, so no connection name or
  ID is configured.
- **The connections the items use, valid in each environment**, with the
  service principal as a user of each: those of the shortcuts of a
  lakehouse to an external source, such as ADLS Gen2, and those of
  `connections`. A connection that signs in with a secret, such as that of
  a service principal, must hold one that is still valid: a lakehouse whose
  shortcut connection holds an expired or replaced secret fails to deploy
  with `AADSTS7000215`.
- **For each mirrored database**, a source of its own per environment, and
  the access at that source of [Mirrored databases](#mirrored-databases).
- **A `.env` file**, copied from `.env.example`, with the credentials of the
  service principal. Keep it out of Git, and never paste its values
  anywhere else.

## Run it

From the root of the repository:

```bash
python scripts/deploy.py --environment prod --plan
```

| Option | What it does |
| :--- | :--- |
| *(none)* | Deploys, activates the value set, starts mirroring, binds and refreshes. For the environment connected to Git, updates it from Git. |
| `--branch` | Instead of `--environment`, runs for the environment whose `branch` matches, such as `--branch main`. |
| `--plan` | Prints what a run would send, delete or update from Git, and changes nothing. |
| `--reconcile` | Reports how the workspace stands against the repository, including the active value sets and the mirroring of each mirrored database, or the Git status for the environment connected to Git, and changes nothing. Exits with 1 when anything differs, an orphan included. |
| `--workspace` | Runs for another workspace than the one of the file. |
| `--source` | Reads the items from another folder than `fabric-workspace`. |
| `--no-refresh` | Binds the models but does not refresh them. |
| `--allow-deletions` | Deletes the orphans of the workspace, but those that hold data and those of `keep`. Without it, they are only reported. |
| `--log-level` | How much pyfabricops logs as the run goes: `INFO` by default, which names each definition it reads; `DEBUG` for each API call, payloads included. |

## Deploy from CI

The pipeline runs the same script, and names no environment of its own: a
first job runs `scripts/environments.py --branch <branch>`, which prints
the environment whose `branch` matches, and the deployment runs in the
environment of that name. By default, `develop` updates dev from Git, as
it is connected to Git; `main` deploys to prod; any other branch deploys
to nothing, and its run succeeds.

| | Azure DevOps | GitHub Actions |
| :--- | :--- | :--- |
| Definition | `azure-pipelines/deploy.yml` | `.github/workflows/deploy.yml` |
| Credentials | the variable group `fabric` | the secrets of the environments `dev` and `prod` |
| Environment of a run | the first stage reads it from `environments/`; one stage per name of the `environments` parameter, and only the one of the branch runs | the first job reads it from `environments/`; the deployment job runs in it |
| Adding an environment | its file, and its name in the `environments` parameter | its file |
| Approval | an Approval check on the environment `prod` | required reviewers on the environment `prod` |
| One run at a time | an Exclusive Lock check on each environment | `concurrency`, per environment |
| Repository access | read only | `permissions: contents: read` |

In Azure DevOps, create the pipeline from **Existing Azure Pipelines YAML
file**, pointing at `azure-pipelines/deploy.yml`. Allow it to use the
variable group and the environments, or **Permit** them on the first run;
until then, a run fails with "Variable group was not found or is not
authorized for use". In GitHub Actions, create the environments, with their
secrets and reviewers, before the first push: a job creates an environment
it names that does not exist, with no protection rule.

There is no scheduled drift report: every deployment reconciles and sends
back what differs, and `--reconcile` checks a workspace by hand at any time.

## Good to know

- **A model carries no credentials, and an import model arrives empty.**
  That is why each deployed model is bound and refreshed. A workspace without
  a capacity refreshes a model at most eight times a day, and each
  deployment of a model uses one.
- **A scheduled refresh is not part of the definition.** Set it once on the
  model in prod; no deployment sets or changes it.
- **An environment without `valueSet` stays on the default values.** The
  Fabric API documents no way back to them, so the script leaves the active
  value set of such an environment alone.
- **The service principal owns the models it deploys.** It also takes over a
  model first published to the workspace by someone else.
- **Moving a workspace to a capacity, or off one, changes nothing here,**
  unless the repository has items a Pro workspace cannot hold.
- **Pointing an environment at another workspace is safe.** Nothing is
  recorded about the old one, so the first run sends every item to the new
  one.
- **Each run reads every definition of the workspace, once.** That is the
  price of keeping no state: a workspace of dozens of items takes a minute
  or two to compare, and nothing has to be stored, pushed or locked. The
  log names each definition as it is read.
- **A run with nothing to send sends nothing.** Right after a deployment,
  `--reconcile` should report every item in sync. pyfabricops leaves out of
  the comparison what Fabric rewrites by itself, such as the logical ID in
  `.platform`, the `artifactType` of a shortcut or what publishing a data
  agent writes. An item that still comes back different on every run would
  be sent, and an import model refreshed, every time: report it.
- **Dataflow Gen2 creates staging items**, a lakehouse and a warehouse
  named `StagingLakehouseForDataflows_…` and `StagingWarehouseForDataflows_…`.
  They are orphans that hold data, so no run deletes them, but
  `--reconcile` lists them and exits with 1.
