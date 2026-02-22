from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.domain import LifeDomain, DomainName
from typing import List

router = APIRouter()

@router.get("/", response_model=List[LifeDomain])
async def get_domains():
    domains = await LifeDomain.find_all().to_list()
    # Initialize defaults if empty
    if not domains:
        initial_domains = [
            LifeDomain(name=DomainName.HEALTH, definition_of_success="Vibrant energy, fit body, mental clarity.", color="#ec4899"),
            LifeDomain(name=DomainName.WEALTH, definition_of_success="Financial freedom, abundant resources.", color="#10b981"),
            LifeDomain(name=DomainName.RELATIONSHIPS, definition_of_success="Deep connections, loving family, loyal friends.", color="#f43f5e"),
            LifeDomain(name=DomainName.GROWTH, definition_of_success="Continuous learning, skill mastery.", color="#8b5cf6"),
            LifeDomain(name=DomainName.CAREER, definition_of_success="Impactful work, recognition, leadership.", color="#3b82f6"),
            LifeDomain(name=DomainName.SPIRITUALITY, definition_of_success="Inner peace, purpose, connection to source.", color="#f59e0b"),
        ]
        for d in initial_domains:
            await d.insert()
        domains = initial_domains
    
    return domains

@router.put("/{domain_id}", response_model=LifeDomain)
async def update_domain(domain_id: str, payload: dict):
    # Rudimentary partial update for scores
    domain = await LifeDomain.get(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    # Update fields manually for safety or use Pydantic copy
    if "budget_score" in payload: domain.budget_score = payload["budget_score"]
    if "time_score" in payload: domain.time_score = payload["time_score"]
    if "scope_score" in payload: domain.scope_score = payload["scope_score"]
    if "target_score" in payload: domain.target_score = payload["target_score"]
    
    await domain.save()
    return domain
