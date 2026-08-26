from sqlmodel import Field, SQLModel


class Contact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    name: str = ""
    phone_number: str = Field(index=True)
