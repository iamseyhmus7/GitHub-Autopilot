from typing import Optional
from pydantic import BaseModel, Field

class AnalysisRequest(BaseModel):
    github_owner: str = Field(..., description="GitHub kullanıcı veya organizasyon adı", example="Ahmetgrkm")
    repo_name: Optional[str] = Field(None, description="İncelenecek repo adı (Boş bırakılırsa tüm profil taranır)", example="automationexercise-ui-test-framework")
    job_description: str = Field(..., min_length=10, description="Adayın değerlendirileceği iş ilanının detayları", example="3 yıl deneyimli Test Otomasyonu (Selenium, Java) Uzmanı, Clean Code bilen aday arıyoruz.")
