from django.core.management.base import BaseCommand

from apps.chatbot.rag.ingest import run


class Command(BaseCommand):
    help = "(Re)build the RAG knowledge base from current product & business data."

    def handle(self, *args, **options):
        run()
        self.stdout.write(self.style.SUCCESS("Knowledge base ingested."))
