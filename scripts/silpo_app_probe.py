#!/usr/bin/env python3
"""Read-only, low-volume checks of documented Silpo catalogue interfaces.

No user account, cookies, forged browser identity, paid API, bypass attempts,
or bulk extraction. HTTP 401/403/429 means stop; never retry around a block.
Only compact diagnostics are returned: no actual product records are published.
"""
import json
from urllib import error, parse, request

LEGACY="https://api.catalog.ecom.silpo.ua/api/2.0/exec/EcomCatalogGlobal"
MODERN_BASE="https://sf-ecom-api.silpo.ua"
# Public branch identifier for Сільпо, Софіївська Борщагівка, вул. Київська, 36.
SOFIA_BRANCH_ID="1edb734d-0398-6a04-90b8-198a97b604e9"

def summarize_payload(value):
    """Expose structure, not a catalog dump or private session data."""
    out={"payloadType":type(value).__name__}
    if isinstance(value,dict):
        out["topLevelKeys"]=list(value.keys())[:20]
        for key in ("items","products","data","result","results","Items"):
            inner=value.get(key)
            if isinstance(inner,list):
                out["candidateList"]=key
                out["candidateCount"]=len(inner)
                if inner and isinstance(inner[0],dict):
                    out["firstProductKeys"]=list(inner[0].keys())[:28]
                break
            if isinstance(inner,dict):
                out["nestedKeys"]=list(inner.keys())[:18]
                for sub in ("items","products","Items","list"):
                    seq=inner.get(sub)
                    if isinstance(seq,list):
                        out["candidateList"]=key+"."+sub
                        out["candidateCount"]=len(seq)
                        if seq and isinstance(seq[0],dict):
                            out["firstProductKeys"]=list(seq[0].keys())[:28]
                        break
                if "candidateList" in out:break
    elif isinstance(value,list):
        out["candidateList"]="root"
        out["candidateCount"]=len(value)
        if value and isinstance(value[0],dict):
            out["firstProductKeys"]=list(value[0].keys())[:28]
    # Capture at most two anonymous, public sample prices to verify units and
    # product URL format before creating a real catalog collector.
    seq=None
    if isinstance(value,dict):
        seq=value.get("items")
        if seq is None and isinstance(value.get("data"),dict):
            seq=value["data"].get("items")
    if isinstance(seq,list):
        fields=("title","price","oldPrice","displayPrice","displayOldPrice",
                "slug","sectionSlug","branchId","stock","promotions")
        out["priceSamples"]=[]
        for item in seq[:2]:
            if not isinstance(item,dict):continue
            sample={key:item.get(key) for key in fields if key in item}
            promo=sample.get("promotions")
            if isinstance(promo,list):
                sample["promotions"]=[list(p.keys())[:12] if isinstance(p,dict) else type(p).__name__ for p in promo[:2]]
            out["priceSamples"].append(sample)
    return out

def _check(url, payload=None):
    result={"reachable":False}
    headers={"Accept":"application/json","User-Agent":"KoshykTsin-ConnectivityCheck/1.0"}
    body=None
    if payload is not None:
        body=json.dumps(payload,ensure_ascii=False).encode("utf-8")
        headers["Content-Type"]="application/json"
    try:
        req=request.Request(url,data=body,headers=headers,method="POST" if body else "GET")
        with request.urlopen(req,timeout=10) as resp:
            result["httpStatus"]=resp.status
            media=resp.headers.get("Content-Type","")
            if "json" not in media.lower():
                result["contentType"]=media[:70]
                return result
            raw=resp.read(100_001)
            if len(raw)>100_000:
                result["error"]="Response exceeded bounded diagnostic size"
                return result
            try:
                obj=json.loads(raw)
            except ValueError:
                result["error"]="Non-JSON response"
                return result
            result.update(summarize_payload(obj))
            result["reachable"]=True
            return result
    except error.HTTPError as exc:
        result["httpStatus"]=exc.code
        result["error"]="HTTP access refused or unavailable"
    except error.URLError as exc:
        result["error"]="Network request unavailable: "+type(exc.reason).__name__
    except (TimeoutError,OSError) as exc:
        result["error"]=type(exc).__name__
    return result

def probe_catalog():
    # 3-item non-personal search, not a sweep of catalog products.
    legacy_data={
        "method":"GetSimpleCatalogItems",
        "data":{"customFilter":"молоко","filialId":"2405",
                "skuPerPage":3,"pageNumber":1}
    }
    modern_query=parse.urlencode({"search":"молоко","limit":2,"inStock":"true"})
    modern_url=f"{MODERN_BASE}/v1/uk/branches/{SOFIA_BRANCH_ID}/products?{modern_query}"
    return {
        "mode":"anonymous-readonly-diagnostic",
        "note":"Read-only test for the Silpo store at Sofiivska Borshchahivka, Kyivska St 36; prices not yet published",
        "legacy":_check(LEGACY,legacy_data),
        "modern":_check(modern_url),
    }

if __name__=="__main__":
    print(json.dumps(probe_catalog(),ensure_ascii=False))
