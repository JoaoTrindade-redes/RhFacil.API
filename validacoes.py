"""Validações e normalização de documentos do RH Fácil."""

def only_digits(value):
    return "".join(c for c in str(value) if c.isdigit())

def cpf_valid(cpf):
    s=only_digits(cpf)
    if len(s)!=11 or s==s[0]*11:
        return False
    for n in (9,10):
        total=sum(int(s[i])*((n+1)-i) for i in range(n))
        d=(total*10)%11
        if d==10: d=0
        if d!=int(s[n]): return False
    return True

def cnpj_valid(cnpj):
    s=only_digits(cnpj)
    if len(s)!=14 or s==s[0]*14:
        return False
    def calc(base,weights):
        total=sum(int(a)*b for a,b in zip(base,weights))
        rem=total%11
        return "0" if rem<2 else str(11-rem)
    d1=calc(s[:12],[5,4,3,2,9,8,7,6,5,4,3,2])
    d2=calc(s[:12]+d1,[6,5,4,3,2,9,8,7,6,5,4,3,2])
    return s[-2:]==d1+d2
