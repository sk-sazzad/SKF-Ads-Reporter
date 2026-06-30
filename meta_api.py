import os
import requests
from typing import Dict, List, Any


class MetaAdsAPI:
    BASE_URL = "https://graph.facebook.com/v25.0"

    def __init__(self):
        self.access_token = os.environ.get("META_ACCESS_TOKEN")

    def get_insights(self, account_id: str, date_start: str, date_stop: str,
                     level: str = "campaign") -> Dict[str, Any]:
        fields = [
            "campaign_name", "adset_name", "ad_name",
            "spend", "impressions", "reach", "clicks",
            "ctr", "cpc", "cpm",
            "actions", "action_values", "cost_per_action_type",
        ]
        params = {
            "fields": ",".join(fields),
            "time_range": f'{{"since":"{date_start}","until":"{date_stop}"}}',
            "level": level,
            "access_token": self.access_token,
            "limit": 100,
        }
        r = requests.get(f"{self.BASE_URL}/{account_id}/insights", params=params, timeout=30)
        r.raise_for_status()
        result = r.json()
        if "error" in result:
            raise Exception(result["error"].get("message", "Meta API error"))
        campaigns = result.get("data", [])
        return {"campaigns": campaigns, "summary": self._summarize(campaigns),
                "date_start": date_start, "date_stop": date_stop}

    def get_geo_insights(self, account_id: str, date_start: str, date_stop: str) -> List[dict]:
        params = {
            "fields": "spend,impressions,clicks,actions",
            "time_range": f'{{"since":"{date_start}","until":"{date_stop}"}}',
            "breakdowns": "country",
            "access_token": self.access_token,
            "limit": 50,
        }
        r = requests.get(f"{self.BASE_URL}/{account_id}/insights", params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("data", [])

    def get_campaign_status(self, account_id: str) -> List[dict]:
        params = {
            "fields": "id,name,status,effective_status,budget_remaining,daily_budget",
            "access_token": self.access_token,
            "limit": 100,
        }
        r = requests.get(f"{self.BASE_URL}/{account_id}/campaigns", params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("data", [])

    def get_account_balance(self, account_id: str) -> dict:
        params = {
            "fields": "balance,amount_spent,spend_cap,currency",
            "access_token": self.access_token,
        }
        r = requests.get(f"{self.BASE_URL}/{account_id}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def _summarize(self, campaigns: List[Dict]) -> Dict:
        total_spend = total_impressions = total_reach = total_clicks = 0
        total_conversions = 0
        total_revenue = 0.0
        for c in campaigns:
            total_spend += float(c.get("spend", 0))
            total_impressions += int(c.get("impressions", 0))
            total_reach += int(c.get("reach", 0))
            total_clicks += int(c.get("clicks", 0))
            for a in c.get("actions", []):
                if a.get("action_type") in ("purchase", "omni_purchase",
                                             "offsite_conversion.fb_pixel_purchase"):
                    total_conversions += int(float(a.get("value", 0)))
            for av in c.get("action_values", []):
                if av.get("action_type") in ("purchase", "omni_purchase",
                                              "offsite_conversion.fb_pixel_purchase"):
                    total_revenue += float(av.get("value", 0))
        return {
            "total_spend": total_spend,
            "total_impressions": total_impressions,
            "total_reach": total_reach,
            "total_clicks": total_clicks,
            "total_conversions": total_conversions,
            "total_revenue": total_revenue,
            "avg_ctr": (total_clicks / total_impressions * 100) if total_impressions else 0,
            "avg_cpc": (total_spend / total_clicks) if total_clicks else 0,
            "roas": (total_revenue / total_spend) if total_spend else 0,
            "cost_per_conversion": (total_spend / total_conversions) if total_conversions else 0,
            "campaign_count": len(campaigns),
        }
