# Cloud Log Monitor — free GitHub Pages portfolio demo

This add-on publishes a **frontend-only demonstration** of your existing Cloud Log Monitor at no hosting cost for an eligible **public GitHub repository**.

The real FastAPI app, PostgreSQL, Redis, worker, and Docker dashboard are **not replaced or uploaded**. GitHub Pages only runs static HTML, CSS, and JavaScript. The sample logs on the page are 100% fictional and the alerts are generated client-side using the same three rule patterns as `app/detector.py`.

## Install — Windows PowerShell

1. Download and extract `cloud-log-monitor-pages-addon.zip` **into the existing** `C:\Users\jazmi\Documents\cloud-log-monitor-starter` repository. Make sure `docs/index.html` exists in the repository root (next to `compose.yaml`).
2. Run from the repository root:

```powershell
git add docs/index.html docs/.nojekyll README-GITHUB-PAGES.md
git commit -m "Add free interactive GitHub Pages demo"
git push origin main
```

3. Open `https://github.com/Jazminee530/cloud-log-monitor/settings/pages`.
4. Under **Build and deployment** set **Source** to **Deploy from a branch**.
5. Set **Branch** to `main`, **Folder** to `/docs`, then click **Save**.
6. Once GitHub reports deployment success, your demo should be at:

   `https://jazminee530.github.io/cloud-log-monitor/`

The URL is the **expected address**, not verified as live until you publish it. GitHub Pages can take a little time to publish.

## Test locally before publishing

You can double-click `docs/index.html` to open it in a browser; no Docker or Python required. Use its filters and **Reset demo** button to explore the synthetic sample.

## Important distinctions

- Public demo: interactive HTML/CSS/JavaScript with fabricated logs and simulated alert-rule results; no API, database, message queue, authentication, or server connection.
- Local full application: the FastAPI + PostgreSQL + Redis + worker stack running through Docker Compose.
- Do not add `.env`, credentials, real workplace logs, patient data, or SSH keys to this repo or to GitHub Pages.
- If your repository is private and you use GitHub Free, GitHub Pages may not be available; a **public** repository is required on GitHub Free.
- The demo content and code are visible to everyone. Keep the full backend local and continue using Docker to run it.

## Optional: add the site link to your existing README

After the Pages site is active, add:

```markdown
[Try the interactive dashboard demo](https://jazminee530.github.io/cloud-log-monitor/)
```

and in GitHub, edit the repository's **About → Website** field to the same URL.
