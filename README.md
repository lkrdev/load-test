# Looker Load Testing Tool (lkr load-test)

A command-line tool for load testing Looker dashboards, queries, rendered dashboards, and embedded dashboards. This tool helps you simulate multiple users accessing Looker resources to measure performance and identify bottlenecks.


- `lkr load-test dashboard`: Run a load test on a dashboard.
- `lkr load-test query`: Run a load test on a query.
- `lkr load-test render`: Run a load test on a rendered dashboard.
- `lkr load-test embed-observability`: Open dashboards with observability metrics in an embedded context.
- `lkr load-test delete-embed-users`: Delete all embed users that were created by this tool. Identifiable by their first name "Embed".

## How it works
The command line tool is a wrapper around the Looker SDK. It uses the Looker SDK to create concurrent **embed** users to run queries, dashboards, and schedules as unique users.

## Key Features

  - Easy deployment with containers or Cloud Run Job
  - Dashboard load testing (with or without auto refresh)
  - Query execution testing
  - Dashboard rendering testing
  - Embedded dashboard observability testing (with or without auto refresh)
  - Configurable number of concurrent users
  - Adjustable spawn rates
  - Customizable wait times between actions

## Use Cases

- Performance testing of Looker dashboards under load
- Identifying bottlenecks in query execution
- Measuring embedded dashboard performance
- Testing dashboard rendering capabilities
- Validating system behavior with multiple concurrent users

## Using User Attributes
It may be beneficial to use user attributes to run a load test.  For example, if you want to test a dashboard with 100 users, you can use the `attribute` argument. We support basic random operations. File a Github Issues if you need more complex operations.

```
lkr load-test dashboard --dashboard=1 --users=5 --attribute store:5 --model=thelook
lkr load-test dashboard --dashboard=1 --users=5 --attribute store:random.randint(1,100) --model=thelook
```


## Arguments

See all command line arguments [here](./lkr.md)

### Handling multiple values
Attributes, models, and permissions can be specified multiple times to create a list of values. For example if you need multiple models for the user you can do `lkr load-test dashboard --dashboard=1 --users=5 --model=thelook --model=thelook2` will create a user with the models `thelook` and `thelook2`. For attributes, you can do `lkr load-test dashboard --dashboard=1 --users=5 --attribute=store:random.randint(1,100) --attribute=region:west` will create a user with the attributes `store:random.randint(1,100)` and `region:west`.


## Running Locally

Install [uv](https://docs.astral.sh/uv/)

```sh
git clone https://github.com/bwebs/looker-locust-testing
cp .env.example .env
uv run --env-file=.env lkr load-test debug looker

# Run a load test on a query with auto refresh
uv run lkr load-test query --query=BLYyJ70e7HCeBQJrxXanHi --users=1 --run-time=5 --model=thelook --attribute "store:random.randint(1,7000)" --query-async

# Run a load test on a dashboard with auto refresh
uv run lkr load-test dashboard --dashboard=1 --users=5 --run-time=5 --attribute store:random.randint(1,7000) --model=thelook
```

## Running in Docker


```
docker run --pull=always us-central1-docker.pkg.dev/lkr-dev-production/load-tests/cli:latest lkr --client=id=abc --client-secret=123 --base-url=https://your-looker-instance.cloud.looker.com load-test dashboard --dashboard=1 --users=5 --run-time=1

docker run -e LOOKERSDK_CLIENT_ID=abc -e LOOKERSDK_CLIENT_SECRET=123 -e LOOKERSDK_BASE_URL="https://your-looker-instance.cloud.looker.com" -p 8080:8080 --pull=always us-central1-docker.pkg.dev/lkr-dev-production/load-tests/cli:latest lkr load-test embed-observability --model=thelook --dashboard=1 --attribute="store:random.randint(0,7000)" --spawn-rate=1 --users=1 --run-time=2 --completion-timeout=45 --port=8080
```

### Example Deploy with Cloud Run Job

This is an example job to run a load test on a dashboard with 200 users for 10 minutes for dashboard id 1.  Note that the dashboard has [Auto Refresh](https://cloud.google.com/looker/docs/editing-user-defined-dashboards#autorefresh) enabled. If you do not have auto refresh enabled, then the user will load the dashboard and just sit there without running more queries. Cloud Run Jobs let you manage multiple concurrent jobs and scale them up and down as needed with --tasks; this is the fastest easiest way to run a large scale load test.

```
gcloud run jobs create lkr-help-job \
    --image=us-central1-docker.pkg.dev/lkr-dev-production/load-tests/cli:latest \
    --command='lkr' \
    --args='load-test dashboard --dashboard=1 --users=20 --run-time=10 --model=thelook' \
    --project=your-gcp-project-id \
    --region=your-gcp-region \ 
    --set-env-vars=LOOKERSDK_CLIENT_ID=your-client-id,LOOKERSDK_CLIENT_SECRET=your-client-secret,LOOKERSDK_BASE_URL=https://your-looker-instance.com \
    --task-timeout=11m \
    --max-retries=0 \
    --cpu=4 \
    --memory=8Gi \
    --tasks=10 \
    --execute-now
```

> Note: Escaping special characters in the command line is a pain.  You can use a custom delimited in the `--args` argument to pass the arguments as a string. E.g. using the + as a delimiter: `--args=^+^"load-test"+"dashboard"+"--dashboard=YOUR_DASHBOARD_ID"+"--users=2"+"--run-time=5"+"--model=YOUR_LOOKML_MODEL"+"--spawn-rate=.1"+"--attribute=store:random.randint(0,7000)"`

After the job is created, you can see open up [Google Cloud Run Jobs](https://console.cloud.google.com/run/jobs) and iterate from there.

One common pattern is to run multiple jobs with different parameters, testing more than just a single use case. With Cloud Run Jobs, you can run a set of jobs once, edit the configuration with other parameters (e.g., dashboard=1 then query=abc123) and run again. Executing the jobs one after the other will parallelize the different parameters.

## Viewing the results

For dashboard, query, and render tests, the recomenndation is to use the Looker System Activity to view the results. A successful outcome is having the task end gracefully and your target number of users or queries was reached. From there you can analyze database or dashboard performance from within system activity. 

For a more centralized view of the results for each session, consider using `lkr load-test embed-observability` to log observability metrics to logs. This will include each session, dashboard load time, each tile's run time and a full dashboard complete event. Since these are structured logs, you can use your tool of choice to analyze the results or choose to sink them to a data warehouse.

## Known Issues
- If you are using a database connection that requires OAuth, this approach will not work.
- If you are on Looker Core, you will need to be in an embed instance to run this tool. If you are using the query load test, your looker client id and client secret must be an [API only Service Account](https://cloud.google.com/looker/docs/looker-core-user-management#creating_an_api-only_service_account).

