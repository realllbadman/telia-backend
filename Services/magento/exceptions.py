"""
Exceptions personnalisées pour le service Magento

Ce module définit les exceptions spécifiques utilisées par le service
Magento pour une gestion d'erreurs claire et structurée.
"""

from typing import Optional


class MagentoServiceError(Exception):
    """
    Exception de base pour toutes les erreurs du service Magento.
    
    Attributes:
        message: Description de l'erreur
        status_code: Code HTTP associé (optionnel)
        details: Informations supplémentaires sur l'erreur
    """
    
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None,
        details: Optional[dict] = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message
    
    def to_dict(self) -> dict:
        """Convertir l'exception en dictionnaire pour les réponses API."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details
        }


class MagentoConnectionError(MagentoServiceError):
    """
    Erreur de connexion au serveur Magento.
    
    Levée lorsque le serveur Magento est inaccessible,
    timeout de connexion, ou problème réseau.
    """
    
    def __init__(self, message: str = "Impossible de se connecter au serveur Magento"):
        super().__init__(message, status_code=503)


class MagentoAuthenticationError(MagentoServiceError):
    """
    Erreur d'authentification Magento.
    
    Levée lorsque le token d'accès est invalide,
    expiré, ou ne dispose pas des permissions nécessaires.
    """
    
    def __init__(self, message: str = "Authentification Magento échouée - Token invalide ou expiré"):
        super().__init__(message, status_code=401)


class MagentoProductNotFoundError(MagentoServiceError):
    """
    Produit non trouvé dans Magento.
    
    Levée lorsqu'un produit spécifique n'existe pas
    ou n'est pas accessible dans le catalogue.
    """
    
    def __init__(self, product_id: int):
        super().__init__(
            f"Produit avec l'ID {product_id} introuvable dans Magento",
            status_code=404,
            details={"product_id": product_id}
        )


class MagentoRateLimitError(MagentoServiceError):
    """
    Limite de requêtes dépassée.
    
    Levée lorsque l'API Magento retourne une erreur 429 (Too Many Requests).
    """
    
    def __init__(self, retry_after: Optional[int] = None):
        message = "Limite de requêtes Magento dépassée"
        if retry_after:
            message += f" - Réessayer dans {retry_after} secondes"
        super().__init__(message, status_code=429, details={"retry_after": retry_after})


class MagentoDataParsingError(MagentoServiceError):
    """
    Erreur de parsing des données Magento.
    
    Levée lorsque la structure des données retournées par Magento
    ne correspond pas au format attendu.
    """
    
    def __init__(self, message: str = "Erreur lors du parsing des données Magento"):
        super().__init__(message, status_code=500)
