import pytest
from fastapi import HTTPException
from fyd.api import identity, document
from fyd.worker import groups

def test_rejects_forged_gateway_and_other_account(monkeypatch):
    monkeypatch.setenv('FYD_BACKEND_SECRET','private-test-value')
    monkeypatch.setenv('ALLOWED_CLERK_USER_ID','user_dillu')
    with pytest.raises(HTTPException) as error: identity('wrong','user_dillu')
    assert error.value.status_code==401
    with pytest.raises(HTTPException) as error: identity('private-test-value','user_other')
    assert error.value.status_code==403
    assert identity('private-test-value','user_dillu')=='user_dillu'

def test_summary_covers_long_pages_and_last_page():
    pages=['first page\n','x'*65000,'last page\n']
    result=list(groups(pages,20000))
    assert ''.join(result)==''.join(pages)
    assert max(map(len,result))<=20000

def test_document_lookup_always_scoped_to_owner(monkeypatch):
    def query(sql,args):
        assert 'owner=%s' in sql
        assert args==('doc-id','user_dillu')
        return []
    monkeypatch.setattr('fyd.api.rows',query)
    with pytest.raises(HTTPException) as error: document('doc-id','user_dillu')
    assert error.value.status_code==404
