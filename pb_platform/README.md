# pb_platform

Namespace reservado para capacidades compartilhadas da plataforma PinkBlue Vet.

Direcao de uso:
- auth compartilhada
- settings
- persistencia
- shell visual comum
- observabilidade compartilhada

Importante:
- o nome `pb_platform` foi escolhido para evitar colisao com o modulo padrao
  `platform` do Python.
- por enquanto, este namespace e apenas um destino estrutural; a migracao do
  codigo ativo deve ser incremental.
