import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from learning_service.backup import backup_data, restore_data
from learning_service.config import Settings
from learning_service.db import Database
from learning_service.login_gateway import GatewaySettings
from learning_service.operations import monitor, recovery_inventory, verify_recovery
from learning_service.secret_files import env_secret
from test_variant_review import review_env, decide, seed_source, draft_result
from test_learning_service import env


def script(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1]/"scripts"/(name+".py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def test_secret_files_load_for_api_worker_gateway_and_do_not_expose_values(tmp_path, monkeypatch):
    for name in ("LEARNING_ADMIN_SECRET", "LEARNING_ADAPTER_SECRET", "LEARNING_BROWSER_AUTH_SECRET"):
        monkeypatch.delenv(name, raising=False)
        f = tmp_path/name; f.write_text("synthetic-private-value-" + "x"*32 + "\n")
        monkeypatch.setenv(name + "_FILE", str(f))
    s = Settings.from_env(); g = GatewaySettings.from_env()
    assert s.browser_auth_secret == g.assertion_secret and s.admin_secret == s.adapter_secret
    assert "synthetic-private-value" not in repr(s) + repr(g)
    monkeypatch.setenv("LEARNING_ADMIN_SECRET", "conflicting-secret")
    with pytest.raises(ValueError, match="either") as e: Settings.from_env()
    assert "conflicting-secret" not in str(e.value)


@pytest.mark.parametrize("kind", ["missing", "symlink", "directory", "multiline", "oversized", "empty", "invalid_utf8"])
def test_bad_secret_files_fail_closed_without_path_or_value(tmp_path, monkeypatch, kind):
    f=tmp_path/"secret"
    if kind=="symlink": f.symlink_to(tmp_path/"target")
    elif kind=="directory": f.mkdir()
    elif kind != "missing": f.write_bytes({"multiline":b"PRIVATE\nSECOND", "oversized":b"x"*16385, "empty":b"", "invalid_utf8":b"\xff"}[kind])
    monkeypatch.setenv("DD_TEST_SECRET_FILE",str(f))
    with pytest.raises(ValueError) as e: env_secret("DD_TEST_SECRET")
    assert str(f) not in str(e.value) and "PRIVATE" not in str(e.value)


def test_rendered_sidecar_and_independent_settings_are_restricted():
    m=script("check_reuse_compose"); c=m.compose_config("sha256:"+"0"*64,Path('/synthetic-secret-directory'))
    assert m.validate(c)==[]
    for mutation in ("ports","external","worker","provider","capability","image","bind"):
        d=json.loads(json.dumps(c)); s=d['services']['learning-api']
        if mutation=='ports': s['ports']=[{'target':31010,'published':'31010'}]
        if mutation=='external': d['networks']['learning-internal']['internal']=False
        if mutation=='worker': d['services']['learning-worker']['environment']['LEARNING_PROVIDER_TOTAL_BUDGET_MICROS']='1'
        if mutation=='provider': s['environment']['LEARNING_MODEL_EXTERNAL_CALLS_ENABLED']='1'
        if mutation=='capability': s['cap_add']=['NET_ADMIN']
        if mutation=='image': s['image']='dd-learning:latest'
        if mutation=='bind': s['volumes']=[{'type':'bind','source':'/synthetic-private-data'}]
        assert m.validate(d)


def test_reconnect_plan_is_idempotent_bound_to_container_network_operator():
    m=script('reconnect_learning_network')
    c={'id':'old-container','labels':{'com.docker.compose.service':'open-webui','com.docker.compose.project':'open-webui'},'networks':{'open-webui_default':{}}}
    n={'id':'network','name':'dd-learning-synthetic_learning-internal','internal':True,'labels':{'com.docker.compose.project':'dd-learning-synthetic','com.docker.compose.network':'learning-internal'}}
    a=m.plan(c,n,'dd-learning-synthetic','synthetic-operator')
    assert a==m.plan(c,n,'dd-learning-synthetic','synthetic-operator')
    c['id']='recreated-container'; assert m.plan(c,n,'dd-learning-synthetic','synthetic-operator')['plan_sha256']!=a['plan_sha256']
    c['networks'][n['name']]={}; assert m.plan(c,n,'dd-learning-synthetic','synthetic-operator')['action']=='already_connected'
    n['internal']=False
    with pytest.raises(ValueError):m.plan(c,n,'dd-learning-synthetic','synthetic-operator')


def test_monitor_projects_only_alert_codes():
    r=monitor({'status':'ok','jobs':{'oldest_queued_age_seconds':301,'expired_running_leases':1},'external_calls':{'paused':True,'invoice_pending_calls':1,'by_state':{'unknown':1},'private_payload':'PRIVATE'},'learner_id':'PRIVATE'})
    assert r['status']=='attention' and 'PRIVATE' not in json.dumps(r)
    assert r['chat_costs_covered'] is False and 'PROVIDER_USAGE_UNKNOWN' in r['alerts']
    assert monitor({'status':'ok'})['alerts']==[]


def test_complete_learning_recovery_retains_frozen_business_and_unknown_holds(review_env,tmp_path):
    s,db,c,h,job,detail=review_env
    assert decide(review_env).status_code==200
    # A crash during a synthetic call leaves a hold; no real request is made.
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO provider_calls(id,provider_id,operation,model_id,evidence_mode,currency,pricing_reference,reserved_cost_micros,state,created_at) VALUES ('synthetic-call','synthetic','diagnosis','synthetic','synthetic_http','USD','synthetic-price',17,'reserved',datetime('now'))")
        conn.execute("INSERT INTO account_contexts(account_id,learner_id,revision,updated_at) VALUES ('acct-a','learner-a',1,datetime('now')) ON CONFLICT(account_id) DO UPDATE SET learner_id='learner-a'")
    before=recovery_inventory(s.data_dir)
    backup_data(s.data_dir,tmp_path/'backup',writers_stopped=True)
    restore_data(tmp_path/'backup',tmp_path/'restore')
    after=recovery_inventory(tmp_path/'restore')
    assert verify_recovery(before,after)['status']=='passed'
    assert after['unknown_calls']==1 and after['provider_reserved_cost_micros']==17
    after['provider_reserved_cost_micros']=0
    assert verify_recovery(before,after)['status']=='failed'


def test_backup_refuses_nested_destination_and_asset_symlinks(env,tmp_path):
    s,db,_=env
    with pytest.raises(ValueError,match='outside'): backup_data(s.data_dir,s.attachment_dir/'nested')
    (s.attachment_dir/'link').symlink_to(tmp_path/'other')
    with pytest.raises(ValueError,match='symlink'):backup_data(s.data_dir,tmp_path/'backup')
