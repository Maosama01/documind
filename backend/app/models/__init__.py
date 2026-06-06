# Importing models here ensures SQLAlchemy knows about them
# when we call Base.metadata.create_all()
from app.models.user import User
from app.models.document import Document