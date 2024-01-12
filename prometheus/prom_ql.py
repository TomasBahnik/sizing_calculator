from typing import List, Tuple

from shared.utils import find_chars_in_str
from prometheus.prompt_model import PromQuery


def static_labels(label: str) -> str:
    # slice to remove '{' and '}'
    label_items: str = label[1:-1]
    lbl_list = label_items.split(",")
    all_static_labels = [lbl.strip() for lbl in lbl_list if '$' not in lbl]
    return ','.join(all_static_labels)


def count_labels(query: str, counter: int = 0):
    query = strip_replace(query)
    left_cb = query.find("{")
    right_cb = query.find("}")
    if right_cb <= left_cb:
        return counter
    counter += 1
    # continue with the rest of string
    new_query = query[right_cb + 1:]
    return count_labels(new_query, counter=counter)


def prom_labels(prom_query: PromQuery, start: int = 0) -> PromQuery:
    """
    Recursively extract labels (i.e. parts inside {..}) and static labels (those without '$')
    from Prometheus expression used in Grafana dashboard
    :param prom_query PromQuery initialized by raw expression
    :param start index where find function starts with search
    """
    # cpt.prometheus.dashboards_analysis.expr_query
    # sets initial value of prom_query.query to already stripped and replaced expr with labels
    end = len(prom_query.expr)
    prom_query.expr = remove_inner_cbs(prom_query)
    left_cb = prom_query.expr.find("{", start, end)
    right_cb = prom_query.expr.find("}", start, end)
    if right_cb < left_cb:
        raise ValueError(f"Closing brace before opening")
    #  neither '{' or '}' found
    if right_cb == -1 and left_cb == -1:
        # noting to do here
        replace_labels(prom_query)
        return prom_query
    # else block is not necessary
    # slice to extract label incl. '{' and '}'
    label = prom_query.expr[left_cb: right_cb + 1]
    sls = static_labels(label=label)
    prom_query.labels.append(label)
    # noinspection PyTypeChecker
    prom_query.staticLabels.append(sls)
    return prom_labels(prom_query=prom_query, start=right_cb + 1)


LEFT_CB = 1
RIGHT_CB = -1


def extract_labels(prom_query: PromQuery) -> PromQuery:
    """
    Detailed doc string  !!
    TODO based on [${__range_s}s] `__range_s` is classified as static label use `[` and `]`
    to distinguish from real label
    """
    left_cbs: List[int] = find_chars_in_str(prom_query.expr, '{')
    right_cbs: List[int] = find_chars_in_str(prom_query.expr, '}')
    if left_cbs and right_cbs:
        if len(right_cbs) != len(left_cbs):
            raise ValueError(f"{len(right_cbs)} != {len(left_cbs)}: Count of left and right curly braces does not match")
        first_left_cb = left_cbs[0]
        last_right_cb = right_cbs[-1]
        if not any(y > first_left_cb for y in right_cbs):
            raise ValueError(f'Some of right cb < first left cb {right_cbs} < {first_left_cb} ')
        if not any(y < last_right_cb for y in left_cbs):
            raise ValueError(f'Some of left cb > last right cb {left_cbs} > {last_right_cb} ')
        left_tuples: List[Tuple[int, int]] = [(idx, LEFT_CB) for idx in left_cbs]
        right_tuples: List[Tuple[int, int]] = [(idx, RIGHT_CB) for idx in right_cbs]
        #  sort by index
        all_tuples: List[Tuple[int, int]] = sorted(left_tuples + right_tuples, key=lambda x: x[0])
        count = 0
        left_cb = left_tuples[0][0]
        new_label: bool = True
        for t in all_tuples:
            if new_label:
                assert t[1] == LEFT_CB  # start by left cb
                left_cb = t[0]
            count += t[1]
            if count != 0:
                new_label = False
                continue
            else:
                # at the beginning query == expr
                assert t[1] == RIGHT_CB  # end by right cb
                right_cb = t[0] + 1
                # expr is original one - extrac labels from original one which is kept fixed
                label = prom_query.expr[left_cb:right_cb]
                new_label = True
                prom_query.labels.append(label)
                label_name = f'(label_{len(prom_query.labels)})'
                # typer.echo(f'label: {label}')
                # replace labels in query
                prom_query.query = prom_query.query.replace(label, label_name)
                sls: str = static_labels(label=label)
                prom_query.staticLabels.append(sls)
        return prom_query
    else:
        return prom_query


def remove_inner_cbs(prom_query):
    """ When searching for labels the nested curly braces {} around dynamic labels e.g.
    kube_pod_info{namespace=~"${namespace}", pod=~"${pod}", deploymentType=~"${deploymentType}"}"
    are problem so remove them first

    Also handle that seconds range
    [${__range_s}s]
    """
    tmp_expr = prom_query.expr
    if '${' in tmp_expr:
        tmp_expr = tmp_expr.replace('${', '$')
        tmp_expr = tmp_expr.replace('}"', '"')
        tmp_expr = tmp_expr.replace('}s', '')
        # tmp_expr = ''.join(str(tmp_expr).split())
    return tmp_expr


def replace_labels(prom_query: PromQuery):
    """
    Replace actual (dynamic and static) labels by numbered string.
    If the label itself contains `{` as e.g. in
    sum(rate(container_cpu_cfs_throttled_seconds_total{namespace=~"$namespace", image!="", pod=~"${created_by}.*"}
    [$__rate_interval])) by (pod) > 0",
    prom_query.labels contain 2 items one of them empty string - do not replace until
    cpt.prometheus.prom_ql.prom_labels correctly identifies nested {}
    This replacement can be optional
    """
    if '' not in prom_query.labels:  # only if non-empty string
        for i in range(len(prom_query.labels)):
            prom_query.query = prom_query.query.replace(prom_query.labels[i], f'(labels_{i})')


def strip_replace(expr):
    expr = expr.strip()
    # keep correct name because of validation of expressions with existing metrics
    # expr = expr.replace(COMPANY, "my-company")
    return expr


def compact(expr):
    query = expr.replace("\n", "")
    query = ''.join(query.split())
    return strip_replace(query)
