from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class Atributo(str, Enum):
    CORPO = "Corpo"
    MENTE = "Mente"
    ESPIRITO = "Espírito"


PERICIAS = [
    "Atletismo", "Conhecimento", "Condução", "Idiomas",
    "Investigação", "Magia", "Manipulação", "Sobrevivência",
    "Subterfúgio", "Tecnologia",
]


class Stats(BaseModel):
    corpo: int = 1
    mente: int = 1
    espirito: int = 1

    @property
    def saude_max(self) -> int:
        return 5 + self.corpo

    @property
    def postura_max(self) -> int:
        return 5 + self.espirito

    @property
    def vontade_max(self) -> int:
        return 5 + self.mente


class Arma(BaseModel):
    nome: str
    dano_bonus: int
    tipo: str  # melee / ranged / explosive
    maos: int
    dano_fixo: Optional[int] = None


class Armadura(BaseModel):
    nome: str
    reducao: int
    penalidade: Optional[str] = None


class Item(BaseModel):
    nome: str
    quantidade: int = 1


class Sobrevivente(BaseModel):
    nome: str = "Sobrevivente"
    stats: Stats = Stats()
    pericias: list[str] = []
    saude: int = 0
    postura: int = 0
    vontade: int = 0
    fome_marcadores: int = 0
    loucura_marcadores: int = 0
    xp: int = 0

    arma_equipada: Optional[Arma] = None
    armadura_equipada: Optional[Armadura] = None
    inventario: list[Item] = []

    def model_post_init(self, _context):
        self.saude = self.stats.saude_max
        self.postura = self.stats.postura_max
        self.vontade = self.stats.vontade_max


class UpgradeRefugio(BaseModel):
    nome: str
    ativo: bool = False


class Refugio(BaseModel):
    tipo: str = "Residência"
    setor_id: str = ""
    defesa: int = 50
    defesa_max: int = 50
    espaco: int = 5
    espaco_max: int = 5
    tecnologia: int = 5
    tecnologia_max: int = 5
    upgrades: list[UpgradeRefugio] = []


class HordaInfo(BaseModel):
    tipo: str
    quantidade: int
    descricao: str


class SetorInfo(BaseModel):
    id: str
    nome: str
    descricao: str
    conexoes: list[str]
    perigo: int
    features: list[str] = []


class EventoInfo(BaseModel):
    rolagem: int
    titulo: str
    descricao: str
    tipo: str
    requer_teste: bool = False
    atributo: Optional[str] = None
    pericia: Optional[str] = None
    sucesso: Optional[str] = None
    falha: Optional[str] = None
    recompensas: Optional[dict] = None
    leva_encontro: bool = False
    tipo_encontro: Optional[str] = None
    especial: Optional[str] = None


class HexCoordenada(BaseModel):
    q: int = 0
    r: int = 0


class SetorHex(BaseModel):
    tipo: str  # id do tipo de setor (cidade_nova, cidade_velha, etc.)
    coordenadas: HexCoordenada
    caracteristica: str = ""  # característica única deste hex (diferenciar do mesmo tipo)


class FaseDia(str, Enum):
    MANHA = "Manhã"
    TARDE = "Tarde"
    NOITE = "Noite"


class EstadoJogo(BaseModel):
    sobrevivente: Sobrevivente = Sobrevivente()
    refugio: Refugio = Refugio()
    setor_atual: HexCoordenada = HexCoordenada()
    mapa: dict[str, SetorHex] = {}
    dia: int = 1
    hora: float = 6.0
    fase: FaseDia = FaseDia.MANHA
    turno: int = 0
    encerrado: bool = False
    causa_morte: Optional[str] = None
    bitola_atual: int = 0
    locais_visitados: list[str] = []
    acontecimentos_registrados: list[str] = []
    encontros_hoje: int = 0
    horda_atacou_hoje: bool = False
    descansou_hoje: bool = False
    dias_sem_comer: int = 0
