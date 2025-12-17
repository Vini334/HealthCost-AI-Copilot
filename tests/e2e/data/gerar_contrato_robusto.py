"""
Script para gerar PDF de contrato de plano de saude ROBUSTO para testes e2e.
Este contrato e mais detalhado para testar melhor as capacidades do chatbot.

Requer: pip install fpdf2
Uso: python gerar_contrato_robusto.py
"""

from fpdf import FPDF
from pathlib import Path


class ContratoRobustoPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(0, 51, 102)
        self.cell(0, 10, 'CONTRATO DE PLANO DE ASSISTENCIA A SAUDE COLETIVO EMPRESARIAL', align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(0, 0, 0)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 5, 'Registrado na ANS sob no 480.123/24-5', align='C', new_x='LMARGIN', new_y='NEXT')
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}/{{nb}} - Contrato no 2024/PRE-001', align='C')

    def titulo_secao(self, texto):
        if self.will_page_break(40):
            self.add_page()
        self.ln(5)
        self.set_font('Helvetica', 'B', 11)
        self.set_fill_color(0, 51, 102)
        self.set_text_color(255, 255, 255)
        self.cell(0, 8, f'  {texto}', fill=True, new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(0, 0, 0)
        self.ln(3)

    def subtitulo(self, texto):
        self.ln(2)
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(0, 51, 102)
        self.cell(0, 6, texto, new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def paragrafo(self, texto):
        self.set_font('Helvetica', '', 10)
        self.multi_cell(0, 5, texto)
        self.ln(2)

    def item(self, texto, nivel=1):
        self.set_font('Helvetica', '', 10)
        indent = 10 + (nivel - 1) * 5
        self.set_x(indent)
        marcador = '-' if nivel == 1 else 'o' if nivel == 2 else '>'
        self.multi_cell(190 - indent, 5, f"{marcador} {texto}")
        self.ln(1)

    def clausula(self, numero, titulo):
        self.ln(3)
        self.set_font('Helvetica', 'B', 10)
        self.cell(0, 6, f'CLAUSULA {numero} - {titulo}', new_x='LMARGIN', new_y='NEXT')
        self.ln(2)

    def tabela_inicio(self, colunas, larguras):
        self.set_font('Helvetica', 'B', 9)
        self.set_fill_color(0, 51, 102)
        self.set_text_color(255, 255, 255)
        for col, larg in zip(colunas, larguras):
            self.cell(larg, 7, col, border=1, align='C', fill=True)
        self.ln()
        self.set_text_color(0, 0, 0)
        self.set_font('Helvetica', '', 9)

    def tabela_linha(self, valores, larguras, fill=False):
        if fill:
            self.set_fill_color(240, 240, 240)
        for val, larg in zip(valores, larguras):
            self.cell(larg, 6, str(val), border=1, align='C', fill=fill)
        self.ln()


def criar_contrato_robusto():
    """Gera um PDF de contrato detalhado e robusto para testes."""

    output_path = Path(__file__).parent / "contrato_robusto.pdf"

    pdf = ContratoRobustoPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ======================== CAPA ========================
    pdf.set_font('Helvetica', 'B', 18)
    pdf.ln(20)
    pdf.cell(0, 15, 'CONTRATO DE PLANO DE SAUDE', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'COLETIVO EMPRESARIAL', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(10)
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 8, 'PLANO PREMIUM EXECUTIVO', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 8, 'Segmentacao: Ambulatorial + Hospitalar com Obstetricia', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 8, 'Acomodacao: Apartamento', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 8, 'Abrangencia: Nacional', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(15)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, 'Contrato no 2024/PRE-001', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 8, 'Vigencia: 01/01/2024 a 31/12/2024', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(30)
    pdf.set_font('Helvetica', 'I', 10)
    pdf.cell(0, 6, 'Este contrato esta em conformidade com a Lei 9.656/98', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 6, 'e regulamentacoes da Agencia Nacional de Saude Suplementar (ANS)', align='C', new_x='LMARGIN', new_y='NEXT')

    # ======================== IDENTIFICACAO ========================
    pdf.add_page()
    pdf.titulo_secao('1. IDENTIFICACAO DAS PARTES CONTRATANTES')

    pdf.subtitulo('1.1. CONTRATANTE (Estipulante)')
    pdf.paragrafo(
        'Razao Social: INDUSTRIA E COMERCIO METALURGICA BRASIL LTDA\n'
        'CNPJ: 12.345.678/0001-90\n'
        'Inscricao Estadual: 123.456.789.123\n'
        'Endereco: Av. das Industrias, 2500, Galpao 15\n'
        'Bairro: Distrito Industrial\n'
        'Cidade: Sao Paulo/SP - CEP: 04001-000\n'
        'Telefone: (11) 3333-4444\n'
        'E-mail: rh@metalurgicabrasil.com.br\n'
        'Representante Legal: Roberto Carlos Mendes da Silva\n'
        'CPF do Representante: 111.222.333-44\n'
        'Numero de funcionarios: 450 (quatrocentos e cinquenta)'
    )

    pdf.subtitulo('1.2. CONTRATADA (Operadora)')
    pdf.paragrafo(
        'Razao Social: OPERADORA DE PLANOS DE SAUDE VIDA PLENA S/A\n'
        'Nome Fantasia: Vida Plena Saude\n'
        'CNPJ: 98.765.432/0001-10\n'
        'Registro ANS: 312.456\n'
        'Endereco: Rua da Saude, 1000, 10o andar\n'
        'Bairro: Centro\n'
        'Cidade: Sao Paulo/SP - CEP: 01310-100\n'
        'Telefone: 0800 123 4567\n'
        'Central de Atendimento 24h: 0800 999 8888\n'
        'Site: www.vidaplena.com.br\n'
        'E-mail: contratos@vidaplena.com.br'
    )

    # ======================== OBJETO ========================
    pdf.titulo_secao('2. DO OBJETO DO CONTRATO')

    pdf.clausula('2.1', 'DEFINICAO DO OBJETO')
    pdf.paragrafo(
        'O presente contrato tem por objeto a prestacao continuada de servicos de cobertura '
        'de custos assistenciais e procedimentos medicos, hospitalares e odontologicos aos '
        'BENEFICIARIOS vinculados a CONTRATANTE, nas condicoes previstas neste instrumento, '
        'seus anexos e na legislacao aplicavel, especialmente a Lei no 9.656/98 e suas alteracoes, '
        'bem como as Resolucoes Normativas da ANS.'
    )

    pdf.clausula('2.2', 'CARACTERISTICAS DO PLANO')
    pdf.paragrafo('O plano ora contratado possui as seguintes caracteristicas:')
    pdf.item('Denominacao: PLANO PREMIUM EXECUTIVO')
    pdf.item('Codigo do Produto na ANS: 480.123/24-5')
    pdf.item('Segmentacao Assistencial: Ambulatorial + Hospitalar com Obstetricia')
    pdf.item('Tipo de Contratacao: Coletivo Empresarial')
    pdf.item('Modalidade de Pagamento: Pre-pagamento')
    pdf.item('Abrangencia Geografica: Nacional (todos os estados brasileiros)')
    pdf.item('Tipo de Acomodacao: Apartamento individual')
    pdf.item('Regime de Coparticipacao: Sim, conforme Clausula 6')
    pdf.item('Franquia: Nao aplicavel')

    # ======================== BENEFICIARIOS ========================
    pdf.titulo_secao('3. DOS BENEFICIARIOS')

    pdf.clausula('3.1', 'TITULARES')
    pdf.paragrafo(
        'Sao beneficiarios titulares todos os empregados da CONTRATANTE que mantenham '
        'vinculo empregaticio formal (CLT), apos o periodo de experiencia de 90 dias, '
        'bem como diretores estatutarios e estagiarios com contrato superior a 6 meses.'
    )

    pdf.clausula('3.2', 'DEPENDENTES')
    pdf.paragrafo('Poderao ser incluidos como dependentes do titular:')
    pdf.item('Conjuge ou companheiro(a) em uniao estavel documentada')
    pdf.item('Filhos solteiros ate 21 anos de idade')
    pdf.item('Filhos solteiros ate 24 anos, se estudantes universitarios')
    pdf.item('Filhos invalidos de qualquer idade, mediante comprovacao')
    pdf.item('Enteados, nas mesmas condicoes dos filhos')
    pdf.item('Menor sob guarda ou tutela legal')
    pdf.item('Pais e sogros, mediante pagamento de valor adicional conforme tabela')

    pdf.clausula('3.3', 'LIMITE DE DEPENDENTES')
    pdf.paragrafo(
        'Nao ha limite de dependentes por titular, desde que comprovado o vinculo '
        'de dependencia conforme documentacao exigida. Pais e sogros estao limitados '
        'a 2 (dois) por titular, sendo 1 (um) de cada lado.'
    )

    # ======================== COBERTURAS ========================
    pdf.titulo_secao('4. DAS COBERTURAS ASSISTENCIAIS')

    pdf.clausula('4.1', 'COBERTURA AMBULATORIAL')
    pdf.paragrafo('A cobertura ambulatorial compreende:')
    pdf.item('Consultas medicas em numero ilimitado em todas as especialidades')
    pdf.item('Consultas e sessoes com nutricionista: ate 12 sessoes/ano')
    pdf.item('Consultas e sessoes com psicologo: ate 40 sessoes/ano')
    pdf.item('Consultas e sessoes com fonoaudiologo: ate 24 sessoes/ano')
    pdf.item('Consultas e sessoes com terapeuta ocupacional: ate 24 sessoes/ano')
    pdf.item('Exames complementares de diagnostico')
    pdf.item('Procedimentos ambulatoriais listados no Rol da ANS')
    pdf.item('Atendimentos de urgencia e emergencia')
    pdf.item('Remocao inter-hospitalar')

    pdf.clausula('4.2', 'COBERTURA HOSPITALAR')
    pdf.paragrafo('A cobertura hospitalar compreende:')
    pdf.item('Internacoes hospitalares em apartamento individual')
    pdf.item('Internacao em UTI/CTI pelo tempo necessario')
    pdf.item('Honorarios medicos de equipe cirurgica')
    pdf.item('Taxas de sala cirurgica e materiais')
    pdf.item('Medicamentos durante a internacao')
    pdf.item('Diarias de acompanhante para menores de 18 anos')
    pdf.item('Diarias de acompanhante para maiores de 60 anos')
    pdf.item('Procedimentos de alta complexidade (quimioterapia, radioterapia, dialise)')
    pdf.item('Transplantes: cornea, rim, medula ossea, figado e coracao (conforme Rol ANS)')

    pdf.clausula('4.3', 'COBERTURA OBSTETRICA')
    pdf.paragrafo('A cobertura obstetrica compreende:')
    pdf.item('Pre-natal completo: consultas e exames')
    pdf.item('Parto normal ou cesariana')
    pdf.item('Internacao para parto em apartamento')
    pdf.item('Assistencia ao recem-nascido nos primeiros 30 dias')
    pdf.item('Inscricao automatica do recem-nascido por 30 dias')
    pdf.item('Complicacoes da gestacao e puerperio')

    pdf.clausula('4.4', 'COBERTURA ESPECIFICA - TERAPIAS')
    pdf.paragrafo('Limites de sessoes anuais para terapias:')

    larguras = [70, 40, 80]
    pdf.tabela_inicio(['Terapia', 'Sessoes/Ano', 'Observacao'], larguras)
    terapias = [
        ('Fisioterapia', '40', 'Renovavel mediante justificativa'),
        ('Fonoaudiologia', '24', 'Renovavel mediante justificativa'),
        ('Terapia Ocupacional', '24', 'Renovavel mediante justificativa'),
        ('Psicoterapia', '40', 'Renovavel mediante justificativa'),
        ('RPG', '20', 'Incluso no limite de fisioterapia'),
        ('Hidroterapia', '40', 'Incluso no limite de fisioterapia'),
        ('Acupuntura', '10', 'Cobertura obrigatoria ANS'),
        ('Nutricao', '12', 'Para doencas cronicas'),
    ]
    for i, t in enumerate(terapias):
        pdf.tabela_linha(t, larguras, fill=i % 2 == 0)

    pdf.clausula('4.5', 'PROCEDIMENTOS ESPECIAIS COM COBERTURA')
    pdf.paragrafo('O plano cobre os seguintes procedimentos especiais:')
    pdf.item('Cirurgias refrativas (miopia, hipermetropia, astigmatismo) apos 1 ano de contrato')
    pdf.item('Cirurgia bariatrica (obesidade morbida IMC >= 40 ou >= 35 com comorbidades)')
    pdf.item('Implante coclear (surdez neurossensorial bilateral)')
    pdf.item('Proteses e orteses ligadas ao ato cirurgico')
    pdf.item('Tratamento oncologico integral (quimioterapia, radioterapia, hormonioterapia)')
    pdf.item('Medicamentos oncologicos orais para uso domiciliar')
    pdf.item('Home care em casos especificos (mediante avaliacao)')

    # ======================== CARENCIAS ========================
    pdf.titulo_secao('5. DOS PRAZOS DE CARENCIA')

    pdf.clausula('5.1', 'CARENCIAS PARA NOVOS BENEFICIARIOS')
    pdf.paragrafo(
        'Aplica-se carencia para beneficiarios incluidos apos a adesao inicial, '
        'conforme tabela abaixo:'
    )

    larguras = [100, 90]
    pdf.tabela_inicio(['Tipo de Procedimento', 'Prazo de Carencia'], larguras)
    carencias = [
        ('Urgencia e Emergencia', '24 horas'),
        ('Consultas e Exames Simples', '30 dias'),
        ('Exames de Alta Complexidade', '180 dias'),
        ('Terapias', '30 dias'),
        ('Internacoes Clinicas', '180 dias'),
        ('Cirurgias', '180 dias'),
        ('Procedimentos Alta Complexidade', '180 dias'),
        ('Parto a termo', '300 dias'),
        ('Doencas Preexistentes (CPT)', '24 meses'),
    ]
    for i, c in enumerate(carencias):
        pdf.tabela_linha(c, larguras, fill=i % 2 == 0)

    pdf.clausula('5.2', 'ISENCAO DE CARENCIAS')
    pdf.paragrafo('Ficam isentos de carencia:')
    pdf.item('Beneficiarios incluidos nos primeiros 30 dias da vigencia do contrato')
    pdf.item('Recem-nascidos, desde que incluidos em ate 30 dias do nascimento')
    pdf.item('Beneficiarios oriundos de outro plano de saude com portabilidade aprovada')
    pdf.item('Inclusoes por casamento ou uniao estavel, se solicitado em ate 30 dias do evento')
    pdf.item('Inclusoes por nascimento ou adocao, se solicitado em ate 30 dias')

    pdf.clausula('5.3', 'COBERTURA PARCIAL TEMPORARIA (CPT)')
    pdf.paragrafo(
        'Beneficiarios que declararem doencas ou lesoes preexistentes (DLP) na declaracao '
        'de saude estarao sujeitos a Cobertura Parcial Temporaria pelo prazo maximo de '
        '24 meses para eventos cirurgicos, leitos de alta tecnologia e procedimentos de '
        'alta complexidade (PAC) exclusivamente relacionados a doenca declarada.'
    )

    # ======================== COPARTICIPACAO ========================
    pdf.titulo_secao('6. DA COPARTICIPACAO')

    pdf.clausula('6.1', 'VALORES DE COPARTICIPACAO')
    pdf.paragrafo(
        'O beneficiario participara no custeio dos seguintes procedimentos:'
    )

    larguras = [75, 50, 65]
    pdf.tabela_inicio(['Procedimento', '% Coparticipacao', 'Limite Maximo'], larguras)
    copart = [
        ('Consultas Eletivas', '20%', 'R$ 80,00'),
        ('Consultas Pronto-Socorro*', '30%', 'R$ 100,00'),
        ('Exames Simples (lab)', '0%', 'Isento'),
        ('Exames Imagem (RX, US)', '20%', 'R$ 150,00'),
        ('Exames Complexos (TC, RM)', '20%', 'R$ 300,00'),
        ('Fisioterapia (sessao)', '20%', 'R$ 30,00'),
        ('Outras Terapias (sessao)', '20%', 'R$ 40,00'),
        ('Psicoterapia (sessao)', '30%', 'R$ 60,00'),
        ('Internacoes', '0%', 'Isento'),
        ('Cirurgias', '0%', 'Isento'),
        ('Parto', '0%', 'Isento'),
        ('Quimio/Radioterapia', '0%', 'Isento'),
    ]
    for i, c in enumerate(copart):
        pdf.tabela_linha(c, larguras, fill=i % 2 == 0)

    pdf.ln(3)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.paragrafo(
        '* Pronto-Socorro: aplica-se coparticipacao apenas quando NAO caracterizada '
        'urgencia/emergencia. Em urgencia/emergencia real, nao ha coparticipacao.'
    )

    pdf.clausula('6.2', 'TETO ANUAL DE COPARTICIPACAO')
    pdf.paragrafo(
        'Fica estabelecido o teto anual de coparticipacao por beneficiario de R$ 3.000,00 '
        '(tres mil reais). Atingido este valor no ano-calendario, o beneficiario fica isento '
        'de coparticipacao para os procedimentos restantes do periodo.'
    )

    pdf.clausula('6.3', 'COBRANCA DA COPARTICIPACAO')
    pdf.paragrafo(
        'A coparticipacao sera cobrada junto com a mensalidade subsequente a utilizacao, '
        'discriminada em boleto separado enviado ao beneficiario titular, com vencimento '
        'no mesmo dia da mensalidade do plano.'
    )

    # ======================== VALORES ========================
    pdf.titulo_secao('7. DO VALOR E FORMA DE PAGAMENTO')

    pdf.clausula('7.1', 'TABELA DE PRECOS POR FAIXA ETARIA')
    pdf.paragrafo('Os valores mensais por beneficiario sao:')

    larguras = [63, 63, 64]
    pdf.tabela_inicio(['Faixa Etaria', 'Titular (R$)', 'Dependente (R$)'], larguras)
    precos = [
        ('0 a 18 anos', '425,00', '425,00'),
        ('19 a 23 anos', '510,00', '510,00'),
        ('24 a 28 anos', '595,00', '595,00'),
        ('29 a 33 anos', '680,00', '680,00'),
        ('34 a 38 anos', '765,00', '765,00'),
        ('39 a 43 anos', '850,00', '850,00'),
        ('44 a 48 anos', '1.020,00', '1.020,00'),
        ('49 a 53 anos', '1.275,00', '1.275,00'),
        ('54 a 58 anos', '1.615,00', '1.615,00'),
        ('59 anos ou mais', '2.125,00', '2.125,00'),
    ]
    for i, p in enumerate(precos):
        pdf.tabela_linha(p, larguras, fill=i % 2 == 0)

    pdf.clausula('7.2', 'VALORES ESPECIAIS')
    pdf.paragrafo('Valores diferenciados para agregados opcionais:')
    pdf.item('Pais/Sogros: valor da faixa etaria + 25% de adicional')
    pdf.item('Agregados (sem vinculo de dependencia): valor da faixa etaria + 40% de adicional')

    pdf.clausula('7.3', 'FORMA DE PAGAMENTO')
    pdf.paragrafo(
        'O pagamento sera realizado mensalmente pela CONTRATANTE, englobando todos os '
        'beneficiarios, atraves de boleto bancario com vencimento todo dia 10 de cada mes. '
        'A nota fiscal sera emitida ate o 5o dia util do mes.'
    )

    pdf.clausula('7.4', 'ATRASO NO PAGAMENTO')
    pdf.paragrafo('Em caso de atraso no pagamento:')
    pdf.item('Multa de 2% sobre o valor da fatura')
    pdf.item('Juros de mora de 1% ao mes, pro-rata die')
    pdf.item('Apos 60 dias de atraso: suspensao do contrato (art. 13, Lei 9.656/98)')
    pdf.item('Apos 90 dias de atraso: rescisao do contrato')
    pdf.paragrafo(
        'Durante a suspensao, os atendimentos de urgencia e emergencia permanecem garantidos.'
    )

    pdf.clausula('7.5', 'REAJUSTE ANUAL')
    pdf.paragrafo(
        'O reajuste anual sera aplicado no mes de aniversario do contrato (janeiro), '
        'com base no indice de reajuste divulgado pela ANS para planos coletivos, '
        'acrescido de eventual sinistralidade excedente conforme Clausula 7.6.'
    )

    pdf.clausula('7.6', 'REAJUSTE POR SINISTRALIDADE')
    pdf.paragrafo(
        'Caso a sinistralidade do grupo ultrapasse 75% no periodo de apuracao (12 meses), '
        'podera ser aplicado reajuste adicional proporcional ao excedente, limitado a 15% '
        'ao ano, alem do reajuste autorizado pela ANS. A sinistralidade sera calculada pela '
        'formula: (Despesas Assistenciais / Receita de Mensalidades) x 100.'
    )

    # ======================== REDE CREDENCIADA ========================
    pdf.titulo_secao('8. DA REDE CREDENCIADA')

    pdf.clausula('8.1', 'REDE PROPRIA E REFERENCIADA')
    pdf.paragrafo(
        'A CONTRATADA disponibiliza ampla rede credenciada em todo territorio nacional, '
        'com mais de 25.000 prestadores entre hospitais, clinicas, laboratorios e '
        'profissionais de saude. A relacao completa esta disponivel no site e app.'
    )

    pdf.clausula('8.2', 'PRINCIPAIS PRESTADORES - SAO PAULO')
    pdf.paragrafo('Hospitais de referencia na regiao de Sao Paulo:')

    larguras = [85, 55, 50]
    pdf.tabela_inicio(['Hospital', 'Especialidade', 'Categoria'], larguras)
    hospitais = [
        ('Hospital Central Sao Paulo', 'Geral/Alta Complex.', 'Premium'),
        ('Hospital Coracao Paulista', 'Cardiologia', 'Premium'),
        ('Hospital Santa Clara', 'Maternidade', 'Premium'),
        ('Hospital Sao Lucas', 'Geral/Emergencia', 'Standard'),
        ('Hospital Infantil ABC', 'Pediatria', 'Premium'),
        ('Centro Oncologico SP', 'Oncologia', 'Premium'),
        ('Instituto de Ortopedia', 'Ortopedia/Trauma', 'Premium'),
        ('Hospital Oftalmologico', 'Oftalmologia', 'Especializado'),
    ]
    for i, h in enumerate(hospitais):
        pdf.tabela_linha(h, larguras, fill=i % 2 == 0)

    pdf.clausula('8.3', 'CLINICAS E LABORATORIOS')
    pdf.item('Centro de Diagnosticos Imagem Total - Exames de imagem')
    pdf.item('Laboratorio Diagnostico Premium - Analises clinicas')
    pdf.item('Clinica Sao Lucas - Consultas ambulatoriais')
    pdf.item('Centro de Medicina Preventiva - Check-up')
    pdf.item('Fisio Vida - Reabilitacao fisica')
    pdf.item('Centro de Psicologia Aplicada - Saude mental')
    pdf.item('OdontoPlus - Rede odontologica')

    pdf.clausula('8.4', 'ALTERACAO DA REDE')
    pdf.paragrafo(
        'A rede credenciada podera ser alterada pela CONTRATADA, mediante comunicacao '
        'previa de 30 dias aos beneficiarios, garantindo substituicao por prestador '
        'equivalente na mesma regiao, conforme RN 259/2011 da ANS.'
    )

    pdf.clausula('8.5', 'REEMBOLSO')
    pdf.paragrafo(
        'Em caso de utilizacao de prestador nao credenciado, o beneficiario podera '
        'solicitar reembolso limitado a 80% da tabela de referencia da operadora, '
        'desde que o procedimento esteja coberto pelo plano. O reembolso sera '
        'processado em ate 30 dias apos a solicitacao.'
    )

    # ======================== EXCLUSOES ========================
    pdf.titulo_secao('9. DAS EXCLUSOES DE COBERTURA')

    pdf.clausula('9.1', 'PROCEDIMENTOS NAO COBERTOS')
    pdf.paragrafo('Nao estao cobertos pelo presente contrato:')
    pdf.item('Tratamentos esteticos e cirurgias plasticas nao reparadoras')
    pdf.item('Procedimentos experimentais ou nao reconhecidos pelo CFM')
    pdf.item('Tratamentos realizados no exterior')
    pdf.item('Medicamentos para tratamento domiciliar (exceto oncologicos orais e AIH)')
    pdf.item('Tratamentos em SPAs, clinicas de repouso ou emagrecimento')
    pdf.item('Inseminacao artificial e fertilizacao in vitro')
    pdf.item('Transplantes nao previstos no Rol da ANS')
    pdf.item('Tratamentos odontologicos (exceto se incluido plano odontologico)')
    pdf.item('Aparelhos auditivos (exceto implante coclear)')
    pdf.item('Procedimentos para mudanca de sexo (exceto se judicializado)')
    pdf.item('Internacao para dependencia quimica alem de 30 dias/ano')

    pdf.clausula('9.2', 'SITUACOES NAO COBERTAS')
    pdf.paragrafo('Nao ha cobertura para eventos decorrentes de:')
    pdf.item('Lesoes auto-infligidas ou tentativa de suicidio')
    pdf.item('Pratica de esportes radicais ou profissionais')
    pdf.item('Atos de guerra, terrorismo ou catastrofes')
    pdf.item('Uso de drogas ilicitas ou alcoolismo (exceto tratamento de dependencia)')
    pdf.item('Acidentes de trabalho (cobertos pelo INSS/empresa)')

    # ======================== VIGENCIA ========================
    pdf.titulo_secao('10. DA VIGENCIA, RENOVACAO E RESCISAO')

    pdf.clausula('10.1', 'VIGENCIA')
    pdf.paragrafo(
        'O presente contrato tera vigencia de 12 (doze) meses, com inicio em 01/01/2024 '
        'e termino em 31/12/2024.'
    )

    pdf.clausula('10.2', 'RENOVACAO')
    pdf.paragrafo(
        'O contrato sera renovado automaticamente por periodos iguais e sucessivos de '
        '12 meses, salvo manifestacao contraria de qualquer das partes com antecedencia '
        'minima de 60 dias do termino da vigencia.'
    )

    pdf.clausula('10.3', 'RESCISAO PELA CONTRATANTE')
    pdf.paragrafo('A CONTRATANTE podera rescindir o contrato:')
    pdf.item('A qualquer tempo, mediante aviso previo de 60 dias')
    pdf.item('Imediatamente, em caso de descumprimento contratual grave pela CONTRATADA')
    pdf.item('Na data de renovacao, comunicando ate 60 dias antes')

    pdf.clausula('10.4', 'RESCISAO PELA CONTRATADA')
    pdf.paragrafo('A CONTRATADA podera rescindir o contrato apenas:')
    pdf.item('Por fraude ou ma-fe comprovada da CONTRATANTE')
    pdf.item('Por inadimplencia superior a 60 dias')
    pdf.item('Por reducao do numero de beneficiarios abaixo do minimo (30 vidas)')

    pdf.clausula('10.5', 'DIREITOS APOS RESCISAO')
    pdf.paragrafo(
        'Em caso de rescisao ou nao renovacao do contrato coletivo, os beneficiarios '
        'terao direito a portabilidade de carencias para outro plano de saude ou '
        'a contratacao de plano individual/familiar sem carencias, conforme RN 438/2018.'
    )

    # ======================== SAC E OUVIDORIA ========================
    pdf.titulo_secao('11. DO ATENDIMENTO AO BENEFICIARIO')

    pdf.clausula('11.1', 'CANAIS DE ATENDIMENTO')
    pdf.paragrafo('A CONTRATADA disponibiliza os seguintes canais:')
    pdf.item('Central de Atendimento 24h: 0800 999 8888')
    pdf.item('SAC - Servico de Atendimento ao Cliente: 0800 123 4567')
    pdf.item('WhatsApp: (11) 99999-8888')
    pdf.item('E-mail: atendimento@vidaplena.com.br')
    pdf.item('Chat online: www.vidaplena.com.br')
    pdf.item('Aplicativo: Vida Plena Saude (iOS/Android)')

    pdf.clausula('11.2', 'OUVIDORIA')
    pdf.paragrafo(
        'A Ouvidoria e o canal para reclamacoes nao resolvidas pelos canais regulares:\n'
        'Telefone: 0800 777 6666\n'
        'E-mail: ouvidoria@vidaplena.com.br\n'
        'Horario: segunda a sexta, das 8h as 18h'
    )

    pdf.clausula('11.3', 'ANS')
    pdf.paragrafo(
        'O beneficiario podera registrar reclamacao junto a ANS:\n'
        'Disque ANS: 0800 701 9656\n'
        'Site: www.ans.gov.br'
    )

    # ======================== DISPOSICOES GERAIS ========================
    pdf.titulo_secao('12. DAS DISPOSICOES GERAIS')

    pdf.clausula('12.1', 'ALTERACOES CADASTRAIS')
    pdf.paragrafo(
        'A CONTRATANTE compromete-se a comunicar inclusoes e exclusoes de beneficiarios '
        'ate o dia 25 de cada mes, para vigencia no mes seguinte. Alteracoes apos essa '
        'data serao processadas no mes subsequente.'
    )

    pdf.clausula('12.2', 'DOCUMENTO DE IDENTIFICACAO')
    pdf.paragrafo(
        'Sera fornecido a cada beneficiario cartao de identificacao em ate 15 dias '
        'apos a inclusao. O cartao virtual estara disponivel imediatamente no aplicativo.'
    )

    pdf.clausula('12.3', 'AUTORIZACAO PREVIA')
    pdf.paragrafo(
        'Os seguintes procedimentos requerem autorizacao previa:\n'
        '- Internacoes eletivas\n'
        '- Cirurgias programadas\n'
        '- Exames de alto custo (RM, TC, PET-CT)\n'
        '- Terapias apos limite de sessoes\n'
        '- Procedimentos de alta complexidade\n\n'
        'A autorizacao sera dada em ate 24h para exames e 48h para internacoes/cirurgias. '
        'Em urgencia/emergencia, nao e necessaria autorizacao previa.'
    )

    pdf.clausula('12.4', 'POLITICA DE PRIVACIDADE')
    pdf.paragrafo(
        'Os dados pessoais e de saude dos beneficiarios serao tratados conforme a '
        'Lei Geral de Protecao de Dados (LGPD - Lei 13.709/2018), sendo utilizados '
        'exclusivamente para a prestacao dos servicos contratados.'
    )

    pdf.clausula('12.5', 'FORO')
    pdf.paragrafo(
        'Fica eleito o foro da Comarca de Sao Paulo/SP para dirimir quaisquer controversias '
        'oriundas deste contrato, com renuncia a qualquer outro, por mais privilegiado que seja.'
    )

    # ======================== ANEXOS ========================
    pdf.titulo_secao('ANEXOS')
    pdf.paragrafo('Integram o presente contrato os seguintes anexos:')
    pdf.item('Anexo I - Relacao de Beneficiarios')
    pdf.item('Anexo II - Rol de Procedimentos e Eventos em Saude da ANS')
    pdf.item('Anexo III - Rede Credenciada por Estado')
    pdf.item('Anexo IV - Tabela de Coparticipacao Detalhada')
    pdf.item('Anexo V - Manual do Beneficiario')
    pdf.item('Anexo VI - Declaracao de Saude')
    pdf.item('Anexo VII - Carta de Orientacao ao Beneficiario')

    # ======================== ASSINATURAS ========================
    pdf.ln(10)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 10, 'Sao Paulo, 01 de Janeiro de 2024.', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(20)
    pdf.cell(0, 6, '_' * 50, align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 6, 'INDUSTRIA E COMERCIO METALURGICA BRASIL LTDA', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 5, 'Roberto Carlos Mendes da Silva - Diretor', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 5, 'CONTRATANTE', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(15)
    pdf.cell(0, 6, '_' * 50, align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 6, 'OPERADORA DE PLANOS DE SAUDE VIDA PLENA S/A', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 5, 'Maria Helena Costa Santos - Diretora Comercial', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 5, 'CONTRATADA', align='C', new_x='LMARGIN', new_y='NEXT')

    # Testemunhas
    pdf.ln(20)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, 'TESTEMUNHAS:', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(10)
    pdf.cell(90, 6, '_' * 30, align='C')
    pdf.cell(10, 6, '')
    pdf.cell(90, 6, '_' * 30, align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(90, 5, 'Nome:', align='C')
    pdf.cell(10, 5, '')
    pdf.cell(90, 5, 'Nome:', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(90, 5, 'CPF:', align='C')
    pdf.cell(10, 5, '')
    pdf.cell(90, 5, 'CPF:', align='C', new_x='LMARGIN', new_y='NEXT')

    pdf.output(str(output_path))
    print(f"PDF robusto gerado com sucesso: {output_path}")
    print(f"Total de paginas: {pdf.page_no()}")
    return output_path


if __name__ == "__main__":
    criar_contrato_robusto()
