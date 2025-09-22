# working cmd
`uv run lkr load-test dashboard --dashboard=nXJRwDcnj1SY3mz3uJtEJt --users=5 --run-time=5 --attribute "store:random.randint(1,7000)" --model=basic_ecomm`
`uv run lkr load-test run-server`
`uv run lkr load-test cookieless-embed-dashboard   --users 1   --spawn-rate 1   --run-time 1 --debug`
`uv run lkr load-test cookieless-embed-dashboard --dashboard 2 --model basic_ecomm --external-group-id test_group_1 --external-group-id-prefix "" --users 1 --spawn-rate 1 --run-time 1 --debug`

# to get working
`uv run python /usr/local/google/home/bguenther/load-test/lkr/load_test/embed_cookieless_dashboard/embed_server.py`

`uv run python -m lkr load-test cookieless-embed --dashboard <your-dashboard-id> --users 1 --run-time `1


```python
uv run lkr load-test cookieless-embed \
  --dashboard 2 \
  --users 10 \
  --spawn-rate 1 \
  --run-time 5
```


uv run lkr load-test cookieless-embed-dashboard \
  --users 10 \
  --spawn-rate 1 \
  --run-time 5

# test the flask server
`source .venv/bin/activate`
`flask --app lkr/load_test/embed_cookieless/embed_server.py run`
go to crd and open the browser?