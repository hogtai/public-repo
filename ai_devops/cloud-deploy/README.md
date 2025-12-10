<h1 style="color: blue;">GCP Cloud Deploy - Our soon to be integrated CD Tool that deploys applications into our GCP Infrastructure</h1>
<p>This project leverages Google Cloud Deploy to automate the continuous deployment of our applications into Google Kubernetes Engine (GKE) environments within our GCP infrastructure.</p>
<a href="https://www.figma.com/board/3sXAQZC22oeATS5cEJSLRy/CICD-Pipeline-Tooling---Digital-Product---Interactive--Copy-?node-id=0-1&t=6EPOXFSITFgPHp2f-1" target="_blank" rel="noopener noreferrer">
(Figma)</a>
<h2>Replacement for Kubernetes Deploy Helper </h2>
<p>This project serves as a CD replacement for the Kubernetes Deploy Helper aka K8s-deploy helper. Google has deprecated certificate-based authentication into GKE clusters, where our applications are deployed. K8s deploy helper relies on certifcate-based authentication in order to managed our workloads on kubernetes, which is why a Cd replacement tool was needed.</p>

<h2>🌟 Features</h2>
<ul>
  <li>Automated deployment of review apps for feature branches.</li>
  <li>Automated deployment to the staging environment for develop, staging, and integration branches.</li>
  <li>Integration with Doppler for secure secrets and configuration management.</li>
  <li>Dynamic rendering of Kubernetes manifests within each Gitlab Project</li>
  <li>Automated tracking of Cloud Deploy rollout status.</li>
  <li>Automated cleanup of Review App resources via the <code>stop:review</code> job.</li>
</ul>

<h2>📁 File Structure</h2>
<p>Key files and directories in this project include:</p>
<ul>
  <li><code>.gitlab-ci-template.yml</code>: Defines the CI/CD pipeline, including stages and jobs for secrets, review app deployment/stopping, and staging/production deployments.</li>
  <li><code>sample_gitlab-ci.yml</code>: Provides the needed configuration to add to your gitlab project .gitlab-ci.yaml file to integrate Cloud Deploy with your project.</li>
  <li><code>README.md</code>: This file, providing an overview and documentation for the project.</li>
</ul>

<h2>🚀 Contributing </h2>


<h2> Setting Up your Local Dev Environment</h2>
<p>While this project primarily focuses on the CI/CD pipeline, contributing to the pipeline itself requires certain tools and access:</p>
<ul>
  <li><strong>GitLab Account:</strong> Access to the project repository.</li>
  <li><strong>GCP Account and Permissions:</strong> Necessary permissions to interact with Google Cloud Deploy, GKE, and other relevant GCP services.</li>
  <li><strong>Doppler Access:</strong> Access to the Doppler project containing the necessary secrets for deployments.</li>
  <li><strong>Google Cloud SDK:</strong> Installed and configured locally for interacting with GCP.</li>
  <li><strong>Kubectl:</strong> Installed locally for interacting with Kubernetes clusters (useful for testing manifests).</li>
</ul>
<p>Ensure your local environment is authenticated with both GCP and Doppler as required by the pipeline scripts (e.g., via service account keys or other authentication methods).</p>

<h2>❗IMPORTANT REMINDER❗</h2>
<p>Review Apps deployed by this pipeline are temporary and will be automatically stopped after a set period (currently 30 days). They are intended for testing and validation purposes only. Access to Review Apps and Staging environments may require being connected to the Life.Church network or VPN.</p>

<h2>🖥️ Project Access 🖥️</h2>
<p>Access to deployed applications:</p>
<ul>
  <li><strong>Review Apps:</strong> Accessible via hostnames following the pattern <code>review-[branch-slug].site.staging.lifechurch.io</code> (e.g., <code>https://review-my-feature-branch.site.staging.lifechurch.io</code>). These are deployed automatically on branch pushes.</li>
  <li><strong>Staging Environment:</strong> Accessible via a designated staging hostname (details may vary based on application configuration). The staging deployment is typically triggered manually.</li>
</ul>
<p>Refer to the specific application's documentation for exact access details and credentials if required.</p>

## Cloud Deploy Release Names

The synxtax of Cloud Deploy Release names are constructed as follows:

*   **Review Apps Releases:** `r${CI_PROJECT_ID}-${TRUNCATED_SHA}-${TIMESTAMP}`
*   **Staging App Releases:** `stg${CI_PROJECT_ID}-${TRUNCATED_SHA}-${TIMESTAMP}`
*   **Production App Releases:** `stg${CI_PROJECT_ID}-${TRUNCATED_SHA}-${TIMESTAMP}`

Where:

*   `r` or `stg` or `prd`: A prefix indicating whether the release is for a Review App (`r`), Staging environment (`stg`), or Production (`p`).
*   `${CI_PROJECT_ID}`: The ID of the GitLab project.
*   `${TRUNCATED_SHA}`: The first 6 characters of the commit SHA, converted to lowercase.
*   `${TIMESTAMP}`: The timestamp in the format `YYYYMMDD-HHMM` (YearMonthDay-HourMinute) in America/Chicago timezone of when the Cloud Release was created. This is determined by when the Deploy Job is run in Project's Gitlab Pipeline.

This naming convention ensures that each release has a unique identifier, making it easier to track and manage deployments and has to follow Google's naming standards for length and usable characters. This will help you identify which release is yours if you are looking for in the GCP Cloud Deploy Console.

## Rolling back a Cloud Deploy Release

To trigger a rollback in Cloud Deploy via the Google Cloud Console, follow these steps:

Login to the Google Cloud Console, go to Cloud Deploy Dashboard

In the left-hand menu, click on "Delivery pipelines".

Click on the name of your delivery pipeline you want to rollback (Int-Staging or Int-Production)

In the Releases tab, you'll see a list of past releases.

Identify a previous release that was successfully deployed to your desired target (e.g., production or staging). You'll typically see a green checkmark for a successful deployment.

Click the three-dot menu (⋮) next to that release, and select “Promote”.

In the dialog box, choose the target cluster that you want to roll back to (e.g., int-staging or int-production) and confirm.
