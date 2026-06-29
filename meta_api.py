import os
import requests
from typing import Dict, List, Any


class MetaAdsAPI:
    BASE_URL = "https://graph.facebook.com/v25.0"

    def __init__(self):
        self.access_token = os.environ.get("META_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError("META_ACCESS_TOKEN not set")

    def get_insights(
        self,
        account_id: str,
        date_start: str,
        date_stop: str,
        level: str = "campaign",
    ) -> Dict[str, Any]:
        fields = [
            "campaign_name",
            "spend",
            "impressions",
            "reach",
            "clicks",
            "ctr",
            "cpc",
            "actions",
            "action_values",
            "cost_per_action_type",
        ]

        params = {
            "fields": ",".join(fields),
            "time_range": f'{{"since":"{date_start}","until":"{date_stop}"}}',
            "level": level,
            "access_token": self.access_token,
            "limit": 100,
        }

        url = f"{self.BASE_URL}/{account_id}/insights"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()

        if "error" in result:
            raise Exception(result["error"].get("message", "Meta API error"))

        campaigns = result.get("data", [])

        summary = self._summarize(campaigns)
        return {
            "campaigns": campaigns,
            "summary": summary,
            "date_start": date_start,
            "date_stop": date_stop,
        }

    def _summarize(self, campaigns: List[Dict]) -> Dict:
        total_spend = 0.0
        total_impressions = 0
        total_reach = 0
        total_clicks = 0
        total_conversions = 0
        total_revenue = 0.0

        for c in campaigns:
            total_spend += float(c.get("spend", 0))
            total_impressions += int(c.get("impressions", 0))
            total_reach += int(c.get("reach", 0))
            total_clicks += int(c.get("clicks", 0))

            for action in c.get("actions", []):
                if action.get("action_type") in (
                    "purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase"
                ):
                    total_conversions += int(float(action.get("value", 0)))

            for av in c.get("action_values", []):
                if av.get("action_type") in (
                    "purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase"
                ):
                    total_revenue += float(av.get("value", 0))

        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions else 0
        avg_cpc = (total_spend / total_clicks) if total_clicks else 0
        roas = (total_revenue / total_spend) if total_spend else 0
        cost_per_conv = (total_spend / total_conversions) if total_conversions else 0

        return {
            "total_spend": total_spend,
            "total_impressions": total_impressions,
            "total_reach": total_reach,
            "total_clicks": total_clicks,
            "total_conversions": total_conversions,
            "total_revenue": total_revenue,
            "avg_ctr": avg_ctr,
            "avg_cpc": avg_cpc,
            "roas": roas,
            "cost_per_conversion": cost_per_conv,
            "campaign_count": len(campaigns),
        }
