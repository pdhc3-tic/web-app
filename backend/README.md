1. Criar o Ambiente Virtual (venv)

# No Windows:

python -m venv venv

# No Linux/Mac:

python3 -m venv venv

2. Ativar o Ambiente Virtual

# No Windows (Prompt de Comando):

venv\Scripts\activate

# No Windows (PowerShell):

.\venv\Scripts\Activate.ps1

# No Linux/Mac:

source venv/bin/activate

3. Instalar as Dependências
   pip install -r requirements/base.txt

4. Configurar as Variáveis de Ambiente
   4.1. Procure por um arquivo chamado .env.example.

   4.2. Crie uma cópia e renomeie para .env.

   4.3. Preencha as chaves DJANGO_SECRET_KEY e AUTH_SECRET (use as chaves que geramos anteriormente).

5. Preparar o Banco de Dados (Migrations)

# Identifica mudanças nos modelos

python manage.py makemigrations

# Aplica as mudanças ao banco de dados

python manage.py migrate

6. Criar um Superusuário (Opcional)
   python manage.py createsuperuser

7. Iniciar o Servidor
   python manage.py runserver

   # Obs: certifique-se de que a porta iniciada é a mesma de NEXT_PUBLIC_API_URL do .env do frontend

8. Rota admin
   [localhost:8000/admin](http://localhost:8080/admin/)
