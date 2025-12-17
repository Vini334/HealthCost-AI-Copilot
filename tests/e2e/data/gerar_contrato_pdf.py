"""
Script para gerar PDF de contrato de plano de saude para testes e2e.
Requer: pip install fpdf2
"""

from fpdf import FPDF
from pathlib import Path


class ContratoPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 10)
        self.cell(0, 10, 'CONTRATO DE PLANO DE ASSISTENCIA A SAUDE', align='C', new_x='LMARGIN', new_y='NEXT')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}/{{nb}}', align='C')

    def titulo_secao(self, texto):
        # Verifica se há espaço suficiente para o título + conteúdo
        # Se não houver, força nova página
        if self.will_page_break(40):
            self.add_page()
        self.ln(5)
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(0, 51, 102)
        self.cell(0, 8, texto, new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(0, 0, 0)
        self.ln(3)

    def paragrafo(self, texto):
        self.set_font('Helvetica', '', 10)
        self.multi_cell(0, 5, texto)
        self.ln(3)

    def item(self, texto):
        self.set_font('Helvetica', '', 10)
        self.set_x(15)
        self.multi_cell(180, 5, f"- {texto}")
        self.ln(1)


def criar_contrato_pdf():
    """Gera um PDF de contrato de plano de saude simplificado."""

    output_path = Path(__file__).parent / "contrato_plano_saude.pdf"

    pdf = ContratoPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Titulo principal
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Contrato no 2024/001 - Plano Empresarial Premium', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(10)

    # Identificacao das Partes
    pdf.titulo_secao('IDENTIFICACAO DAS PARTES')
    pdf.paragrafo(
        'CONTRATANTE: Empresa Tecnologia ABC Ltda., inscrita no CNPJ sob no 12.345.678/0001-90, '
        'com sede na Av. Paulista, 1000, Sao Paulo/SP, neste ato representada por seu diretor.'
    )
    pdf.paragrafo(
        'CONTRATADA: Operadora Saude Total S/A, inscrita no CNPJ sob no 98.765.432/0001-10, '
        'registrada na ANS sob no 123456, com sede na Rua da Saude, 500, Sao Paulo/SP.'
    )

    # Clausula 1 - Objeto
    pdf.titulo_secao('CLAUSULA 1 - DO OBJETO')
    pdf.paragrafo(
        '1.1. O presente contrato tem por objeto a prestacao de servicos de assistencia a saude '
        'aos beneficiarios vinculados a CONTRATANTE, conforme condicoes estabelecidas neste instrumento '
        'e na legislacao vigente, especialmente a Lei no 9.656/98 e regulamentacoes da ANS.'
    )
    pdf.paragrafo(
        '1.2. O plano contratado e o PLANO EMPRESARIAL PREMIUM, com cobertura nacional, '
        'segmentacao ambulatorial + hospitalar com obstetricia, e acomodacao em apartamento.'
    )

    # Clausula 2 - Cobertura
    pdf.titulo_secao('CLAUSULA 2 - DA COBERTURA ASSISTENCIAL')
    pdf.paragrafo('2.1. A CONTRATADA assegura aos beneficiarios as seguintes coberturas:')
    pdf.item('Consultas medicas em todas as especialidades reconhecidas pelo CFM')
    pdf.item('Exames laboratoriais e de diagnostico por imagem previstos no Rol da ANS')
    pdf.item('Internacoes hospitalares em apartamento, incluindo UTI quando necessario')
    pdf.item('Procedimentos cirurgicos com cobertura integral')
    pdf.item('Atendimento obstetrico, incluindo parto e pre-natal')
    pdf.item('Tratamentos de urgencia e emergencia 24 horas')
    pdf.item('Terapias: fisioterapia (ate 40 sessoes/ano), fonoaudiologia, terapia ocupacional e psicologia')
    pdf.ln(3)
    pdf.paragrafo(
        '2.2. Carencias: Para novos beneficiarios incluidos apos a adesao inicial: '
        '24 horas para urgencia/emergencia; 30 dias para consultas e exames simples; '
        '180 dias para internacoes e procedimentos de alta complexidade; 300 dias para parto.'
    )

    # Clausula 3 - Valores
    pdf.titulo_secao('CLAUSULA 3 - DO VALOR E FORMA DE PAGAMENTO')
    pdf.paragrafo(
        '3.1. O valor mensal por beneficiario titular e de R$ 850,00 (oitocentos e cinquenta reais), '
        'com os seguintes valores para dependentes por faixa etaria:'
    )
    pdf.ln(3)

    # Tabela de valores
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(0, 51, 102)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(95, 7, 'Faixa Etaria', border=1, align='C', fill=True)
    pdf.cell(95, 7, 'Valor Mensal (R$)', border=1, align='C', fill=True, new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Helvetica', '', 9)

    faixas = [
        ('0 a 18 anos', '425,00'),
        ('19 a 23 anos', '510,00'),
        ('24 a 28 anos', '595,00'),
        ('29 a 33 anos', '680,00'),
        ('34 a 38 anos', '765,00'),
        ('39 a 43 anos', '850,00'),
        ('44 a 48 anos', '1.020,00'),
        ('49 a 53 anos', '1.275,00'),
        ('54 a 58 anos', '1.615,00'),
        ('59 anos ou mais', '2.125,00'),
    ]

    for i, (faixa, valor) in enumerate(faixas):
        fill = i % 2 == 0
        if fill:
            pdf.set_fill_color(240, 240, 240)
        pdf.cell(95, 6, faixa, border=1, align='C', fill=fill)
        pdf.cell(95, 6, valor, border=1, align='C', fill=fill, new_x='LMARGIN', new_y='NEXT')

    pdf.ln(5)
    pdf.paragrafo(
        '3.2. O pagamento sera realizado ate o dia 10 de cada mes, mediante boleto bancario. '
        'O atraso superior a 60 dias autoriza a suspensao do contrato, conforme art. 13, paragrafo unico, II da Lei 9.656/98.'
    )
    pdf.paragrafo(
        '3.3. O reajuste anual sera aplicado no mes de aniversario do contrato, com base no indice '
        'autorizado pela ANS para planos coletivos.'
    )

    # Clausula 4 - Coparticipacao
    pdf.titulo_secao('CLAUSULA 4 - DA COPARTICIPACAO')
    pdf.paragrafo('4.1. O presente plano preve coparticipacao do beneficiario nos seguintes procedimentos:')
    pdf.item('Consultas eletivas: 20% do valor de referencia, limitado a R$ 80,00 por consulta')
    pdf.item('Exames simples (laboratoriais): sem coparticipacao')
    pdf.item('Exames de imagem: 20% do valor de referencia, limitado a R$ 300,00')
    pdf.item('Fisioterapia e terapias: 20% por sessao, limitado a R$ 30,00')
    pdf.item('Internacoes e cirurgias: sem coparticipacao')
    pdf.item('Pronto-socorro (casos nao caracterizados como urgencia/emergencia): R$ 100,00 por atendimento')

    # Clausula 5 - Rede
    pdf.titulo_secao('CLAUSULA 5 - DA REDE CREDENCIADA')
    pdf.paragrafo(
        '5.1. A CONTRATADA disponibiliza rede credenciada propria e referenciada em todo territorio nacional, '
        'incluindo os seguintes estabelecimentos na regiao de Sao Paulo:'
    )
    pdf.item('Hospital Central Sao Paulo - Referencia em alta complexidade')
    pdf.item('Hospital Maternidade Santa Clara - Referencia em obstetricia')
    pdf.item('Clinica Sao Lucas - Consultas e procedimentos ambulatoriais')
    pdf.item('Centro de Diagnosticos Imagem Total - Exames de imagem')
    pdf.item('Laboratorio Diagnostico - Exames laboratoriais')
    pdf.item('Fisio Vida - Centro de reabilitacao')
    pdf.ln(2)
    pdf.paragrafo(
        '5.2. A lista completa de prestadores esta disponivel no site www.saudetotal.com.br/rede '
        'e no aplicativo movel da operadora.'
    )

    # Clausula 6 - Vigencia
    pdf.titulo_secao('CLAUSULA 6 - DA VIGENCIA E RESCISAO')
    pdf.paragrafo(
        '6.1. O presente contrato vigorara pelo prazo de 12 (doze) meses, com inicio em 01/01/2024 '
        'e termino em 31/12/2024, renovando-se automaticamente por periodos iguais e sucessivos.'
    )
    pdf.paragrafo('6.2. A rescisao podera ocorrer:')
    pdf.item('Por acordo entre as partes, a qualquer momento')
    pdf.item('Por denuncia unilateral da CONTRATANTE, mediante aviso previo de 60 dias')
    pdf.item('Por inadimplemento superior a 60 dias')
    pdf.item('Por fraude ou declaracao falsa do beneficiario')

    # Clausula 7 - Exclusoes
    pdf.titulo_secao('CLAUSULA 7 - DAS EXCLUSOES DE COBERTURA')
    pdf.paragrafo('7.1. Nao estao cobertos pelo presente contrato:')
    pdf.item('Procedimentos esteticos e cirurgias plasticas nao reparadoras')
    pdf.item('Tratamentos experimentais nao reconhecidos pela ANS')
    pdf.item('Procedimentos realizados no exterior')
    pdf.item('Medicamentos para uso domiciliar, exceto antineoplasicos orais')
    pdf.item('Tratamentos em SPAs e clinicas de repouso')
    pdf.item('Transplantes nao listados no Rol da ANS')
    pdf.item('Inseminacao artificial e fertilizacao in vitro')

    # Clausula 8 - Disposicoes Gerais
    pdf.titulo_secao('CLAUSULA 8 - DISPOSICOES GERAIS')
    pdf.paragrafo(
        '8.1. A CONTRATANTE compromete-se a manter atualizado o cadastro de beneficiarios, '
        'informando inclusoes e exclusoes ate o dia 25 de cada mes para vigencia no mes seguinte.'
    )
    pdf.paragrafo(
        '8.2. Fica eleito o foro da Comarca de Sao Paulo/SP para dirimir quaisquer questoes '
        'oriundas deste contrato, com renuncia a qualquer outro, por mais privilegiado que seja.'
    )

    # Assinaturas
    pdf.ln(10)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 10, 'Sao Paulo, 01 de Janeiro de 2024.', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(15)
    pdf.cell(90, 5, '_' * 35, align='C')
    pdf.cell(10, 5, '')
    pdf.cell(90, 5, '_' * 35, align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(90, 5, 'CONTRATANTE', align='C')
    pdf.cell(10, 5, '')
    pdf.cell(90, 5, 'CONTRATADA', align='C', new_x='LMARGIN', new_y='NEXT')

    pdf.output(str(output_path))
    print(f"PDF gerado com sucesso: {output_path}")
    return output_path


if __name__ == "__main__":
    criar_contrato_pdf()
