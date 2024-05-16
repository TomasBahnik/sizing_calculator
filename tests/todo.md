# Add tests

* all 3 namespace cases (None, existing, non-existing)
* time delta `-d`
* start-end `-s` `e`

## load-metrics

command example :  `./main.py load-metrics -f ./sla_tables/tmp/ -d 0.2 -n namespace`

## last-update

all namespaces `./main.py last-update -f ./sla_tables/tmp/`
existing namespaces `./main.py last-update -f ./sla_tables/tmp/ -n namespace`
non-existing namespaces `./main.py last-update -f ./sla_tables/tmp/ -n fgfsagsag`

## eval-slas
empty rules - no data for e.g.
Too many null!!

`./main.py eval-slas -f ./sla_tables/tmp/ -d 1`

## load-save-df

`./main.py load-save-df -d 1`

## sizing-reports

### Sample
`./main.py sizing-reports -f ./sla_tables/tmp/ -s 2024-05-16T08:00:00+00:00 -e  2024-05-16T08:12:00+00:00 -n namespace`

### Bugs
all namespaces (no `-n` option)

```text
 File "/home/toba/git/github/sizing_calculator/./main.py", line 83, in sizing_reports
    assert len(namespaces) == 1
           ^^^^^^^^^^^^^^^^^^^^
```

delta specified (`./main.py sizing-reports -f ./sla_tables/tmp/ -d 0.3`)

```text
  File "/home/toba/git/github/sizing_calculator/./main.py", line 121, in sizing_reports
    raise ValueError("Either start_time and end_time or test_summary_file must be provided")

ValueError: Either start_time and end_time or test_summary_file must be provided
```

