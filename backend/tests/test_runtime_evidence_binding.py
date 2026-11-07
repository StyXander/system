"""Synthetic exact-text bindings and parser cache identities, not research gold."""
import pytest
from scripts.bind_validation_runtime import bind_ids
from backend.tests.test_matter_connectivity import reports


def evidence(eid,text,sha='synthetic',page=1):
    return {'evidence_id':eid,'quote':text,'document_id':'SYN-D','source_sha256':sha,'pdf_page':page,'source_verified':True,'invalid_reason':''}


def test_one_block_can_bind_to_two_exact_same_page_fragments():
    ids,mapping=bind_ids([evidence('OLD','合成目标\n合成结果')],[evidence('A','合成目标'),evidence('B','合成结果')],['OLD'])
    assert ids==['A','B'] and mapping=={'OLD':['A','B']}


def test_unmatched_text_cannot_be_silently_dropped_or_paraphrased():
    with pytest.raises(ValueError,match='UNAVAILABLE'):
        bind_ids([evidence('OLD','合成完整证据')],[evidence('A','合成证据')],['OLD'])


def test_same_text_from_a_different_hash_or_page_cannot_be_bound():
    for replacement in [evidence('A','原文',sha='changed'),evidence('A','原文',page=2)]:
        with pytest.raises(ValueError,match='UNAVAILABLE'):bind_ids([evidence('OLD','原文')],[replacement],['OLD'])


def test_an_existing_id_cannot_hide_changed_provenance():
    with pytest.raises(ValueError,match='COLLISION'):
        bind_ids([evidence('A','原文')],[evidence('A','原文',sha='changed')],['A'])


def test_parser_version_is_part_of_cache_identity(reports,monkeypatch):
    import pymupdf
    from backend.app.connectivity_extraction import load_registry
    from backend.app.connectivity_matter_extraction import read_corpus
    root,_=reports;docs=load_registry(root)[:1]
    _,first=read_corpus(root,docs)
    _,second=read_corpus(root,docs)
    assert second[0]['cache_hit']
    monkeypatch.setattr(pymupdf,'VersionBind','synthetic-other-version')
    _,changed=read_corpus(root,docs)
    assert not changed[0]['cache_hit']
    assert changed[0]['parser_version']=='synthetic-other-version'
