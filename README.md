# OpenCode Conversation

Une custom integration Home Assistant (compatible installation manuelle HACS)
qui remplace l'agent Conversation natif par un agent [OpenCode Server]. Chaque
prompt Conversation est transféré à OpenCode via HTTP Basic Auth et la réponse
textuelle est renvoyée à Home Assistant pour affichage/TTS.

> Cette intégration ne prend volontairement **pas** en charge HA CONTROL :
> OpenCode ne pilote pas directement Home Assistant par son intermédiaire.

## Installation

1. Copiez le répertoire `custom_components/opencode_conversation` dans
   `<config>/custom_components/opencode_conversation`, ou ajoutez ce dépôt avec
   **HACS → Integrations → Custom repositories** puis téléchargez-le.
2. Redémarrez Home Assistant.
3. Ajoutez **OpenCode Conversation** dans *Settings → Devices & services → Add
   integration*.

## Serveur et sécurité

Démarrez OpenCode Server avec sa protection Basic Auth native, de manière à ce
que Home Assistant puisse le joindre :

```sh
OPENCODE_SERVER_USERNAME=opencode \
OPENCODE_SERVER_PASSWORD='choose-a-long-random-password' \
opencode serve --hostname 0.0.0.0 --port 4096
```

Renseignez ensuite le même username/password dans l'intégration et l'URL du
serveur (par exemple `https://opencode.example.internal`). **N'exposez pas
OpenCode directement sur Internet.** Utilisez HTTPS via un proxy inverse ou un
réseau Docker privé, avec des identifiants distincts et un pare-feu. Le mot de
passe est stocké dans le stockage de configuration Home Assistant ; ne le
publiez pas dans un fichier YAML ou des journaux.

## Configuration

Le formulaire demande :

- **URL** — racine du serveur OpenCode, sans chemin d'API ;
- **Username** — `opencode` par défaut ;
- **Password** — mot de passe Basic Auth ;
- **Agent** — `ha-assist` par défaut, qui doit apparaître dans `GET /agent` ;
- **Timeout** — délai HTTP total, 90 secondes par défaut.

À la configuration, l'intégration valide `GET /global/health`, `GET /agent` et
l'agent choisi. Une entrée est unique par couple URL + agent. Les refus
d'authentification déclenchent une réauthentification, sans afficher les détails
du serveur ni les identifiants dans la réponse vocale.

## Comportement

- Chaque `conversation_id` Home Assistant est associé en mémoire à une session
  OpenCode créée avec `POST /session`, puis utilisée via
  `POST /session/{id}/message`.
- Les accès concurrents à une même conversation sont sérialisés. Les mappings
  expirent après six heures d'inactivité et sont plafonnés à 100.
- Seules les parts OpenCode de type `text` sont ajoutées au `ChatLog` et
  prononcées ; les appels d'outils, métadonnées et contenus inconnus sont
  ignorés.
- En cas de panne, une phrase neutre est retournée au lieu d'une stack trace ou
  d'une donnée sensible.

Pour transférer *tous* les prompts à OpenCode, sélectionnez cet agent de
conversation comme agent préféré et désactivez la gestion locale des commandes
dans votre pipeline/assistant vocal Home Assistant. Sinon, des commandes locales
peuvent être consommées avant d'arriver à l'agent distant.

## Développement

Les tests présents sont volontairement indépendants de Home Assistant et
vérifient les fonctions pures du client. Installez explicitement les outils de
test, puis lancez :

```sh
python3 -m pip install -e '.[test]'
python3 -m pytest
python3 -m compileall custom_components
```

L'exécution réelle nécessite une installation Home Assistant actuelle : les
tests unitaires ne valident ni le config flow ni l'enregistrement du runtime.

[OpenCode Server]: https://opencode.ai
