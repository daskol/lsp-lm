class CompletionProtocol(LanguageServerProtocol):

    def __init__(self, completor_loader, session):
        super().__init__()

        self.completor: AbstractCompletor
        self.completor_loader = completor_loader
        self.session = session

    def watch_pid(self, pid: int):
        logging.info('watch for process with pid %d', <mask>)
