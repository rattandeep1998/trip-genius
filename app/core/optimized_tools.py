import os
import json
import requests
import heapq
from typing import List, Dict, Any, Tuple
from langchain.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

class ItinerarySuggestionTool(BaseTool):
    name: str = "itinerary_suggestion"
    description: str = "Generates optimized travel itineraries using TripAdvisor data and graph algorithms."

    def fetch_tripadvisor_data(self, location: str) -> List[Dict[str, Any]]:
        tripadvisor_api_key = os.getenv('TRIPADVISOR_API_KEY')
        if not tripadvisor_api_key:
            raise ValueError("TripAdvisor API key not found. Set TRIPADVISOR_API_KEY.")

        url = f"https://api.content.tripadvisor.com/api/v1/location/search"
        params = {
            "searchQuery": location,
            "language": "en",
            "key": tripadvisor_api_key
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        attractions = [
            {"name": item["name"], "latitude": item["latitude"], "longitude": item["longitude"]}
            for item in data.get("data", []) if "latitude" in item and "longitude" in item
        ]
        return attractions

    def build_graph(self, attractions: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        def haversine(lat1, lon1, lat2, lon2):
            from math import radians, sin, cos, sqrt, atan2
            R = 6371
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
            return 2 * R * atan2(sqrt(a), sqrt(1 - a))

        graph = {}
        for i, attr1 in enumerate(attractions):
            graph[attr1["name"]] = {}
            for j, attr2 in enumerate(attractions):
                if i != j:
                    distance = haversine(attr1["latitude"], attr1["longitude"], attr2["latitude"], attr2["longitude"])
                    graph[attr1["name"]][attr2["name"]] = distance
        return graph

    def find_optimal_path(self, graph: Dict[str, Dict[str, float]], start: str) -> List[str]:
        visited = set()
        path = [start]
        current = start

        while len(visited) < len(graph):
            visited.add(current)
            neighbors = [(neighbor, distance) for neighbor, distance in graph[current].items() if neighbor not in visited]
            if not neighbors:
                break
            next_node = min(neighbors, key=lambda x: x[1])[0]
            path.append(next_node)
            current = next_node

        return path

    def _run(self, destinationCity: str, verbose: bool = True) -> Dict[str, Any]:
        try:
            attractions = self.fetch_tripadvisor_data(destinationCity)
            if verbose:
                print(f"Fetched {len(attractions)} attractions from TripAdvisor.")

            graph = self.build_graph(attractions)
            start_location = attractions[0]["name"] if attractions else None
            if not start_location:
                return {"error": "No attractions found for the destination."}

            optimal_path = self.find_optimal_path(graph, start_location)

            if verbose:
                print(f"Optimal Path: {optimal_path}")

            system_prompt = f"""
            You are an expert travel planner. Based on the following attractions, create a detailed day-by-day itinerary.

            Attractions in optimized order: {', '.join(optimal_path)}

            Include:
            - Detailed descriptions
            - Recommended times to visit
            - Suggested nearby restaurants
            """

            llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "Generate an optimized itinerary.")
            ])

            chain = prompt | llm
            response = chain.invoke({"query": "Generate an optimized itinerary."})

            itinerary = {
                "travel_plan": response.content,
                "optimal_path": optimal_path
            }

            return itinerary

        except Exception as e:
            return {"error": str(e)}
