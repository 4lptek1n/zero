# GitHub Actions workflow template

The release script that pushed this repo to GitHub used an OAuth token
that intentionally lacks the `workflow` scope, so it cannot create
files under `.github/workflows/` directly.

To enable CI on your fork:

```bash
mkdir -p .github/workflows
cp docs/github-workflow-template/ci.yml .github/workflows/ci.yml
git add .github/workflows/ci.yml
git commit -m "ci: enable GitHub Actions"
git push
```

Once the file lives under `.github/workflows/`, GitHub picks it up
automatically on the next push and PR.
