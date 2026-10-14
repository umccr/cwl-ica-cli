# Product

## Overview

`cwl-ica` is a command-line tool for creating, validating, registering, and syncing
[CWL](https://www.commonwl.org/) (Common Workflow Language) workflows from a GitHub
repository to Illumina's ICA (Illumina Connected Analytics) platform, across multiple
tenants and projects.

It is maintained by [UMCCR](https://github.com/umccr) and is the CLI companion to the
[cwl-ica](https://github.com/umccr/cwl-ica) workflow repository. See the
[project wiki](https://github.com/umccr/cwl-ica/wiki) to get started.

## What it does

The CLI operates against a separate git repository (the "cwl-ica repo", located via the
`CWL_ICA_REPO_PATH` environment variable) that holds the CWL definitions and a set of
config YAMLs. Core capabilities:

- **Configure** the local environment: point at the cwl-ica repo, map tenant IDs to
  names, and register users.
- **Create** CWL expressions, schemas, tools, and workflows from templates.
- **Validate** CWL artifacts (and TypeScript expressions) before registration.
- **Register/Init** artifacts into the repo config YAMLs and onto ICA projects.
- **Sync** artifact definitions and md5sums between the repo and ICA.
- **Manage projects**: add tools/workflows to projects, link projects, set defaults.
- **Release** workflows to GitHub and build release assets.
- **Generate** submission templates and markdown catalogue/help documentation.
- **GitHub Actions** helpers that run the sync/markdown/catalogue steps in CI.
- **ICAv2 (v2) integrations**: manage v2 tenants, projects, datasets, bunches, and zip
  workflows into ICAv2 pipelines.

## Concepts

- **Tenant** — an ICA tenancy; each project belongs to a tenant.
- **Project** — an ICA project that workflows/tools are deployed into.
- **Expression / Schema / Tool / Workflow** — the four CWL artifact types, each with a
  versioned lifecycle: create-from-template → validate → init → sync.
- **Config YAMLs** — `project.yaml`, `category.yaml`, `tenant.yaml`, `user.yaml`,
  `tool.yaml`, `workflow.yaml`, etc. live in the cwl-ica repo's `config/` directory and
  act as the registry of known artifacts.

## Audience

Bioinformatics/workflow engineers at UMCCR (and collaborators) who author CWL workflows
and deploy them to ICA. Users interact exclusively through the `cwl-ica` command.
