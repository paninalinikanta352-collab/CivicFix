from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field

Role = Literal['user', 'worker', 'admin']
Category = Literal['roads', 'water', 'electricity', 'cleanliness', 'other']
IssueStatus = Literal['reported', 'assigned', 'in_progress', 'resolved', 'rejected']

class UserRegister(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserPublic(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: Role
    created_at: str
    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: UserPublic

class IssueCreate(BaseModel):
    title: str = Field(min_length=4, max_length=160)
    description: str = Field(min_length=8, max_length=5000)
    category: Category = 'other'
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = Field(default=None, max_length=500)

class IssuePatch(BaseModel):
    title: str | None = Field(default=None, min_length=4, max_length=160)
    description: str | None = Field(default=None, min_length=8, max_length=5000)
    category: Category | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = Field(default=None, max_length=500)
    model_config = ConfigDict(extra='forbid')

class StatusUpdate(BaseModel):
    status: IssueStatus
    note: str | None = Field(default=None, max_length=1000)

class AssignWorker(BaseModel):
    worker_id: int

class WorkerCreate(UserRegister):
    pass

class IssuePublic(BaseModel):
    id: int
    title: str
    description: str
    category: Category
    latitude: float | None
    longitude: float | None
    address: str | None
    photo_url: str | None
    risk_percentage: int
    status: IssueStatus
    reporter_id: int
    assigned_worker_id: int | None
    ai_analysis: str | None = None
    created_at: str
    updated_at: str

class IssueList(BaseModel):
    items: list[IssuePublic]
    total: int
    limit: int
    offset: int

class IssueUpdatePublic(BaseModel):
    id: int
    issue_id: int
    actor_id: int
    status: IssueStatus
    note: str | None
    created_at: str
