import os

import aiohttp
import asyncio
from fastapi import FastAPI, HTTPException
from yarl import URL
import gidgethub.aiohttp

GITHUB_URL = URL("https://github.com")
GALLERY_URL = URL("http://gallery.pangeo.io")
GALLERY_REPO = "pangeo-gallery/pangeo-gallery"
OAUTH_TOKEN = os.environ['GITHUB_TOKEN']
REQUESTER = 'pangeo-gallery-bot'

_session = None

async def get_session():
   global _session
   if _session is None:
       _session =  aiohttp.ClientSession()
   return _session

app = FastAPI()

@app.get("/gallery/submodule-dispatch/{github_org}/{github_repo}",
         status_code=204)
async def dispatch(github_org: str, github_repo: str):
    session = await get_session()

    # make sure the github repo exists
    repo_url = GITHUB_URL / github_org / github_repo
    resp = await session.get(repo_url)
    if resp.status != 200:
        raise HTTPException(status_code=500,
                            detail=f"Repo {repo_url} not found")

    # make sure the repo is part of the gallery
    gh = gidgethub.aiohttp.GitHubAPI(session, REQUESTER,
                                     oauth_token=OAUTH_TOKEN)
    data = await gh.getitem(f"/repos/{GALLERY_REPO}/commits/master")
    master_sha = data['sha']
    master_tree = await gh.getitem(f"/repos/{GALLERY_REPO}/git/trees/{master_sha}")
    repo_sha = [tree['sha'] for tree in master_tree['tree'] if tree['path']=='repos']
    assert len(repo_sha)==1
    repo_sha = repo_sha[0]
    repo_tree = await gh.getitem(f"/repos/{GALLERY_REPO}/git/trees/{repo_sha}?recursive=1")
    submodule_paths = [tree['path'] for tree in repo_tree['tree']]
    submodule_path = '/'.join([github_org, github_repo])
    if submodule_path not in submodule_paths:
        raise HTTPException(status_code=500,
                            detail=f"Submodule {submodule_path} not found in {GALLERY_REPO}")

    # all good, do repository dispatch
    dispatch_data = {'event_type': 'update-gallery',
                     'client_payload': {'repository': submodule_path}}
    await gh.post(f"/repos/{GALLERY_REPO}/dispatches", data=dispatch_data)
