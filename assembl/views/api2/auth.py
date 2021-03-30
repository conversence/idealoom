from builtins import str
from simplejson import dumps, loads
import logging
from datetime import datetime

from Levenshtein import jaro_winkler
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.settings import asbool
from pyramid.security import (
    authenticated_userid, Everyone, NO_PERMISSION_REQUIRED, remember, forget)
from pyramid.i18n import TranslationStringFactory
from pyramid.httpexceptions import (
    HTTPNotFound, HTTPUnauthorized, HTTPBadRequest, HTTPClientError,
    HTTPOk, HTTPNoContent, HTTPForbidden, HTTPNotImplemented, HTTPError,
    HTTPPreconditionFailed, HTTPConflict)
from pyisemail import is_email
from sqlalchemy.sql.expression import literal

import assembl.lib.config as settings
from assembl.lib.web_token import decode_token, TokenInvalid
from assembl.lib.sqla_types import EmailString
from assembl.lib.text_search import add_simple_text_search
from assembl.auth import (
    P_ADMIN_DISC, P_SELF_REGISTER, P_SELF_REGISTER_REQUEST,
    R_PARTICIPANT, P_READ, CrudPermissions)
from assembl.auth.social_auth import maybe_social_logout
from assembl.models import (
    User, Discussion, LocalUserRole, AbstractAgentAccount, AgentProfile,
    UserLanguagePreference, EmailAccount, AgentStatusInDiscussion)
from assembl.auth.password import (
    verify_password_change_token, get_data_token_time, Validity)
from assembl.auth.util import discussion_from_request
from ..traversal import (CollectionContext, InstanceContext, ClassContext)
from ..errors import ErrorTypes
from .. import JSONError
from . import (
    FORM_HEADER, JSON_HEADER, collection_view, instance_put_json,
    collection_add_json, instance_view, check_permissions, CreationResponse)
from assembl.lib.sqla import ObjectNotUniqueError
from ..auth.views import (
    send_change_password_email, from_identifier, send_confirmation_email,
    maybe_auto_subscribe)

_ = TranslationStringFactory('assembl')
log = logging.getLogger(__name__)

TOKEN_SECRET = settings.get('session.secret')


@view_config(
    context=ClassContext, request_method="PATCH",
    ctx_class=LocalUserRole)
@view_config(
    context=ClassContext, request_method="PUT",
    ctx_class=LocalUserRole)
@view_config(
    context=ClassContext, request_method="POST",
    ctx_class=LocalUserRole)
def add_local_role_on_class(request):
    # Did not securize this route, so forbid it.
    raise HTTPNotFound()


@view_config(
    context=CollectionContext, request_method="POST",
    ctx_named_collection="Discussion.local_user_roles",
    header=JSON_HEADER, renderer='json')
@view_config(
    context=CollectionContext, request_method="POST",
    ctx_named_collection="User.local_roles",
    header=JSON_HEADER, renderer='json')
def add_local_role(request):
    # Do not use check_permissions, this is a special case
    ctx = request.context
    user_id = authenticated_userid(request)
    if not user_id:
        raise HTTPUnauthorized()
    discussion_id = ctx.get_discussion_id()
    discussion = Discussion.get(discussion_id)
    user_uri = User.uri_generic(user_id)
    if discussion_id is None:
        raise HTTPBadRequest()
    permissions = ctx.get_permissions()
    json = request.json_body
    if "discussion" not in json:
        json["discussion"] = Discussion.uri_generic(discussion_id)
    requested_user = json.get('user', None)
    if not requested_user:
        json['user'] = requested_user = user_uri
    elif requested_user != user_uri and P_ADMIN_DISC not in permissions:
        raise HTTPUnauthorized()
    if P_ADMIN_DISC not in permissions:
        if P_SELF_REGISTER in permissions:
            json['requested'] = False
            json['role'] = R_PARTICIPANT
            req_user = User.get_instance(requested_user)
            if not discussion.check_authorized_email(req_user):
                raise HTTPForbidden()
        elif P_SELF_REGISTER_REQUEST in permissions:
            json['requested'] = True
        else:
            raise HTTPUnauthorized()
    try:
        instances = ctx.create_object("LocalUserRole", json)
    except HTTPClientError as e:
        raise e
    except Exception as e:
        raise HTTPBadRequest(e)
    if instances:
        first = instances[0]
        db = first.db
        for instance in instances:
            db.add(instance)
        db.flush()
        # Side effect: materialize subscriptions.
        if not first.requested:
            # relationship may not be initialized
            user = first.user or User.get(first.user_id)
            user.get_notification_subscriptions(discussion_id, True, request)

        # Update the user's AgentStatusInDiscussion
        user.update_agent_status_subscribe(discussion)

        view = request.GET.get('view', None) or 'default'
        return CreationResponse(first, user_id, permissions, view)


@view_config(
    context=InstanceContext, request_method="PATCH",
    ctx_named_collection_instance="Discussion.local_user_roles",
    header=JSON_HEADER, renderer='json')
@view_config(
    context=InstanceContext, request_method="PATCH",
    ctx_named_collection_instance="User.local_roles",
    header=JSON_HEADER, renderer='json')
@view_config(
    context=InstanceContext, request_method="PUT",
    ctx_named_collection_instance="Discussion.local_user_roles",
    header=JSON_HEADER, renderer='json')
@view_config(
    context=InstanceContext, request_method="PUT",
    ctx_named_collection_instance="User.local_roles",
    header=JSON_HEADER, renderer='json')
def set_local_role(request):
    # Do not use check_permissions, this is a special case
    ctx = request.context
    instance = ctx._instance
    user_id = authenticated_userid(request)
    if not user_id:
        raise HTTPUnauthorized()
    discussion_id = ctx.get_discussion_id()
    user_uri = User.uri_generic(user_id)
    if discussion_id is None:
        raise HTTPBadRequest()
    permissions = ctx.get_permissions()
    json = request.json_body
    requested_user = json.get('user', None)
    if not requested_user:
        json['user'] = requested_user = user_uri
    elif requested_user != user_uri and P_ADMIN_DISC not in permissions:
        raise HTTPUnauthorized()
    if P_ADMIN_DISC not in permissions:
        if P_SELF_REGISTER in permissions:
            json['requested'] = False
            json['role'] = R_PARTICIPANT
        elif P_SELF_REGISTER_REQUEST in permissions:
            json['requested'] = True
        else:
            raise HTTPUnauthorized()
    updated = instance.update_from_json(json, user_id, ctx)
    view = request.GET.get('view', None) or 'default'

    # Update the user's AgentStatusInDiscussion
    user = User.get(user_id)
    discussion = Discussion.get(discussion_id)
    user.update_agent_status_subscribe(discussion)

    if view == 'id_only':
        return [updated.uri()]
    else:
        return updated.generic_json(view, user_id, permissions)


@view_config(
    context=InstanceContext, request_method='DELETE',
    ctx_named_collection_instance="Discussion.local_user_roles",
    renderer='json')
@view_config(
    context=InstanceContext, request_method='DELETE',
    ctx_named_collection_instance="User.local_roles",
    renderer='json')
def delete_local_role(request):
    ctx = request.context
    instance = ctx._instance
    user_id = authenticated_userid(request)
    if not user_id:
        raise HTTPUnauthorized()
    discussion_id = ctx.get_discussion_id()

    if discussion_id is None:
        raise HTTPBadRequest()
    permissions = ctx.get_permissions()
    requested_user = instance.user
    if requested_user.id != user_id and P_ADMIN_DISC not in permissions:
        raise HTTPUnauthorized()

    user = User.get(user_id)
    discussion = Discussion.get(discussion_id)
    instance.db.delete(instance)
    # Update the user's AgentStatusInDiscussion
    user.update_agent_status_unsubscribe(discussion)
    instance.db.flush()  # maybe unnecessary
    return {}


@view_config(
    context=CollectionContext, request_method="POST",
    ctx_named_collection="Discussion.local_user_roles",
    header=FORM_HEADER)
@view_config(
    context=CollectionContext, request_method="POST",
    ctx_named_collection="User.local_roles",
    header=FORM_HEADER)
def use_json_header_for_LocalUserRole_POST(request):
    raise HTTPNotFound()


@view_config(
    context=CollectionContext, request_method="PUT",
    ctx_named_collection="Discussion.local_user_roles",
    header=FORM_HEADER)
@view_config(
    context=CollectionContext, request_method="PUT",
    ctx_named_collection="User.local_roles",
    header=FORM_HEADER)
def use_json_header_for_LocalUserRole_PUT(request):
    raise HTTPNotFound()


@view_config(context=CollectionContext, renderer='json', request_method='GET',
             ctx_collection_class=LocalUserRole,
             accept="application/json")
def view_localuserrole_collection(request):
    return collection_view(request, 'default')


@view_config(context=CollectionContext, renderer='json', request_method='GET',
             ctx_collection_class=AgentProfile,
             accept="application/json", permission=P_READ)
def view_profile_collection(request):
    ctx = request.context
    view = request.GET.get('view', None) or ctx.get_default_view() or 'default'
    content = collection_view(request)
    if view != "id_only":
        discussion = ctx.get_instance_of_class(Discussion)
        if discussion:
            from assembl.models import Post, AgentProfile
            num_posts_per_user = \
                AgentProfile.count_posts_in_discussion_all_profiles(discussion)
            for x in content:
                id = AgentProfile.get_database_id(x['@id'])
                if id in num_posts_per_user:
                    x['post_count'] = num_posts_per_user[id]
    return content


@view_config(context=InstanceContext, renderer='json', request_method='GET',
             ctx_instance_class=AgentProfile,
             accept="application/json", permission=P_READ)
def view_agent_profile(request):
    profile = instance_view(request)
    if isinstance(profile, HTTPError):
        raise profile
    ctx = request.context
    view = ctx.get_default_view() or 'default'
    view = request.GET.get('view', view)
    if view not in ("id_only", "extended"):
        discussion = ctx.get_instance_of_class(Discussion)
        if discussion:
            profile['post_count'] = ctx._instance.count_posts_in_discussion(
                discussion.id)
    return profile


@view_config(
    context=InstanceContext, ctx_instance_class=AbstractAgentAccount,
    request_method='POST', name="verify", renderer='json')
def send_account_verification(request):
    ctx = request.context
    instance = ctx._instance
    if instance.verified:
        return HTTPNoContent(
            "No need to verify email <%s>" % (instance.email))
    request.matchdict = {}
    send_confirmation_email(request, instance)
    return {}


# Should I add a secure_connection condition?
@view_config(
    context=InstanceContext, ctx_instance_class=User,
    request_method='POST', name="verify_password", renderer='json')
def verify_password(request):
    ctx = request.context
    user = ctx._instance
    password = request.params.get('password', None)
    if password is None:
        raise HTTPBadRequest("Please provide a password")
    result = user.check_password(password)
    if result:
        user.successful_login()
    return result


@view_config(
    context=CollectionContext, ctx_instance_class=User,
    request_method='POST', permission=NO_PERMISSION_REQUIRED,
    name="logout", renderer='json')
def logout(request):
    logout_url = maybe_social_logout(request)
    forget(request)
    # Interesting question: Should I add a parameter
    # to log out of the social service?


@view_config(
    context=CollectionContext, ctx_collection_class=AgentProfile,
    request_method='POST', permission=NO_PERMISSION_REQUIRED,
    name="password_reset", header=JSON_HEADER)
@view_config(
    context=ClassContext, ctx_class=AgentProfile, header=JSON_HEADER,
    request_method='POST', permission=NO_PERMISSION_REQUIRED,
    name="password_reset")
def reset_password(request):
    identifier = request.json_body.get('identifier')
    user_id = request.json_body.get('user_id')
    slug = request.json_body.get('discussion_slug')
    discussion = None
    if slug:
        discussion = Discussion.default_db.query(
            Discussion).filter_by(slug=slug).first()
    email = None
    user = None
    localizer = request.localizer

    if user_id:
        user = AgentProfile.get(int(user_id))
        if not user:
            raise JSONError(
                localizer.translate(_("The user does not exist")),
                code=HTTPNotFound.code)
        if identifier:
            for account in user.accounts:
                if identifier == account.email:
                    email = identifier
                    break
    elif identifier:
        user, account = from_identifier(identifier)
        if not user:
            raise JSONError(
                localizer.translate(_("This email does not exist")),
                code=HTTPNotFound.code)
        if account:
            email = account.email
    else:
        error = localizer.translate(_("Please give an identifier"))
        raise JSONError(error)
    if not email:
        email = user.get_preferred_email()
    if not email:
        error = localizer.translate(_("This user has no email"))
        raise JSONError(error, code=HTTPPreconditionFailed.code)
    if not isinstance(user, User):
        error = localizer.translate(_("This is not a user"))
        raise JSONError(error, code=HTTPPreconditionFailed.code)
    send_change_password_email(request, user, email, discussion=discussion)
    return HTTPOk()


@view_config(
    context=CollectionContext, ctx_collection_class=AgentProfile,
    request_method='POST', permission=NO_PERMISSION_REQUIRED,
    name="do_password_change", header=JSON_HEADER)
@view_config(
    context=ClassContext, ctx_class=AgentProfile, header=JSON_HEADER,
    request_method='POST', permission=NO_PERMISSION_REQUIRED,
    name="do_password_change")
def do_password_change(request):
    token = request.json_body.get('token') or ''
    password = request.json_body.get('password') or ''
    # TODO: Check password quality!
    localizer = request.localizer
    user, validity = verify_password_change_token(token)
    token_date = get_data_token_time(token)
    old_token = (
        user is None or token_date is None or (
            user.last_login and token_date < user.last_login))

    if (validity != Validity.VALID or old_token):
        # V-, V+P+W-B-L-: Invalid or obsolete token (obsolete+logged in treated later.)
        # Offer to send a new token
        if validity != Validity.VALID:
            error = localizer.translate(_(
                "This link is not valid. Do you want us to send another?"))
        else:
            error = localizer.translate(_(
                "This link has been used. Do you want us to send another?"))
        raise JSONError(error, validity)
    user.password_p = password
    user.successful_login()
    headers = remember(request, user.id)
    request.response.headerlist.extend(headers)
    return HTTPOk()


@view_config(
    context=CollectionContext, ctx_collection_class=AgentProfile,
    request_method='POST', header=JSON_HEADER,
    permission=NO_PERMISSION_REQUIRED)
@view_config(
    context=ClassContext, ctx_class=User, header=JSON_HEADER,
    request_method='POST', permission=NO_PERMISSION_REQUIRED)
def assembl_register_user(request):
    forget(request)
    localizer = request.localizer
    session = AgentProfile.default_db
    json = request.json
    discussion = discussion_from_request(request)
    permissions = ctx.get_permissions()

    name = json.get('real_name', '').strip()
    errors = JSONError()
    if not name or len(name) < 3:
        errors.add_error(localizer.translate(_(
            "Please use a name of at least 3 characters")),
            ErrorTypes.SHORT_NAME)
    password = json.get('password', '').strip()
    # TODO: Check password strength. maybe pwdmeter?
    email = None
    for account in json.get('accounts', ()):
        email = account.get('email', None)
        if not is_email(email):
            errors.add_error(localizer.translate(_(
                "This is not a valid email")),
                ErrorTypes.INVALID_EMAIL)
            continue
        email = EmailString.normalize_email_case(email)
        # Find agent account to avoid duplicates!
        if session.query(AbstractAgentAccount).filter_by(
                email_ci=email).count():
            errors.add_error(localizer.translate(_(
                "We already have a user with this email.")),
                ErrorTypes.EXISTING_EMAIL,
                HTTPConflict.code)
    if not email:
        errors.add_error(localizer.translate(_("No email.")),
                         ErrorTypes.INVALID_EMAIL)
    username = json.get('username', None)
    if username and session.query(User).filter_by(username=username).count():
        errors.add_error(localizer.translate(_(
            "We already have a user with this username.")),
            ErrorTypes.EXISTING_USERNAME,
            HTTPConflict.code)

    if errors:
        raise errors

    validate_registration = asbool(settings.get(
        'idealoom_validate_registration_emails'))

    old_autoflush = session.autoflush
    session.autoflush = False
    try:
        now = datetime.utcnow()

        user = User(
            name=name,
            password=password,
            verified=not validate_registration,
            creation_date=now
        )

        session.add(user)
        session.flush()

        user.update_from_json(json, user_id=user.id)
        if discussion and not (
                P_SELF_REGISTER in permissions or
                P_SELF_REGISTER_REQUEST in permissions):
            # Consider it without context
            discussion = None
        if discussion:
            agent_status = AgentStatusInDiscussion(
                agent_profile=user, discussion=discussion,
                first_visit=now, last_visit=now,
                user_created_on_this_discussion=True)
            session.add(agent_status)
        session.flush()
        account = user.accounts[0]
        email = account.email
        account.verified = not validate_registration

        if validate_registration:
            send_confirmation_email(request, account)
        else:
            user.verified = True
            for account in user.accounts:
                account.verified = True
            user.successful_login()
            if asbool(settings.get('pyramid.debug_authorization')):
                # for debugging purposes
                from assembl.auth.password import email_token
                log.info("email token: " + request.route_url(
                         'user_confirm_email', token=email_token(account)))
            if discussion:
                maybe_auto_subscribe(user, discussion)
        session.flush()
        return CreationResponse(user, Everyone, permissions)
    finally:
        session.autoflush = old_autoflush


@view_config(
    context=InstanceContext, ctx_instance_class=AbstractAgentAccount,
    request_method='DELETE', renderer='json')
def delete_abstract_agent_account(request):
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = ctx.get_permissions()
    instance = ctx._instance
    if not instance.user_can(user_id, CrudPermissions.DELETE, permissions):
        raise HTTPUnauthorized()
    if instance.email:
        accounts_with_mail = [a for a in instance.profile.accounts if a.email]
        if len(accounts_with_mail) == 1:
            raise JSONError("This is the last account")
        if instance.verified:
            verified_accounts_with_mail = [
                a for a in accounts_with_mail if a.verified]
            if len(verified_accounts_with_mail) == 1:
                raise JSONError("This is the last verified account", code=403)
    instance.db.delete(instance)
    return {}


@view_config(context=InstanceContext, request_method='PATCH',
             header=JSON_HEADER, ctx_instance_class=AbstractAgentAccount,
             renderer='json')
@view_config(context=InstanceContext, request_method='PUT', header=JSON_HEADER,
             ctx_instance_class=AbstractAgentAccount, renderer='json')
def put_abstract_agent_account(request):
    instance = request.context._instance
    old_preferred = instance.preferred
    new_preferred = request.json_body.get('preferred', False)
    if new_preferred and not instance.email:
        raise HTTPForbidden("Cannot prefer an account without email")
    if new_preferred and not instance.verified:
        raise HTTPForbidden("Cannot set a non-verified email as preferred")
    result = instance_put_json(request)
    assert instance.preferred == new_preferred
    if new_preferred and not old_preferred:
        for account in instance.profile.accounts:
            if account != instance:
                account.preferred = False
    return result


@view_config(context=CollectionContext, request_method='POST',
             header=JSON_HEADER, ctx_collection_class=AbstractAgentAccount)
def post_email_account(request):
    from assembl.views.auth.views import send_confirmation_email
    response = collection_add_json(request)
    request.matchdict = {}
    instance = request.context.collection_class.get_instance(response.location)
    send_confirmation_email(request, instance)
    return response


def set_user_dis_connected(request, connecting):
    ctx = request.context
    discussion_id = ctx.get_discussion_id()
    if not discussion_id:
        # This view should only exist in discussion+user context
        raise HTTPNotFound()
    token = request.POST.get('token')
    # see if token corresponds to user
    user = ctx.get_instance_of_class(User)
    if not token:
        raise HTTPUnauthorized()
    try:
        token = decode_token(token, TOKEN_SECRET)
        assert token['userId'] == user.id
    except TokenInvalid:
        raise HTTPUnauthorized()

    status = user.get_status_in_discussion(discussion_id)
    assert status
    if connecting:
        status.last_connected = datetime.now()
    else:
        status.last_disconnected = datetime.now()
    return HTTPOk()


@view_config(context=InstanceContext, request_method='POST',
             ctx_instance_class=AgentProfile, name="connecting")
def set_user_connected(request):
    return set_user_dis_connected(request, True)


@view_config(context=InstanceContext, request_method='POST',
             ctx_instance_class=AgentProfile, name="disconnecting")
def set_user_disconnected(request):
    return set_user_dis_connected(request, False)


@view_config(
    context=InstanceContext, request_method='GET',
    ctx_instance_class=AgentProfile,
    renderer='json', name='interesting_ideas')
def interesting_ideas(request):
    from .discussion import get_analytics_alerts
    ctx = request.context
    target = request.context._instance
    user_id = authenticated_userid(request) or Everyone
    discussion_id = ctx.get_discussion_id()
    permissions = ctx.get_permissions()
    if P_READ not in permissions:
        raise HTTPUnauthorized()
    if user_id != target.id and P_ADMIN_DISC not in permissions:
        raise HTTPUnauthorized()
    discussion = Discussion.get(discussion_id)
    if not discussion:
        raise HTTPNotFound()
    result = get_analytics_alerts(
        discussion, target.id,
        ["interesting_to_me"], False)
    result = loads(result)['responses'][0]['data'][0]['suggestions']
    result = {x['targetID']: x['arguments']['score'] for x in result}
    return result


@view_config(context=CollectionContext, request_method='POST', renderer="json",
             header=JSON_HEADER, ctx_collection_class=UserLanguagePreference)
def add_user_language_preference(request):
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = ctx.get_permissions()
    check_permissions(ctx, user_id, CrudPermissions.CREATE)
    typename = ctx.collection_class.external_typename()
    json = request.json_body
    try:
        instances = ctx.create_object(typename, json)
    except ObjectNotUniqueError as e:
        raise JSONError(str(e), code=409)
    except Exception as e:
        raise HTTPBadRequest(e)
    if instances:
        first = instances[0]
        db = first.db
        for instance in instances:
            db.add(instance)
        db.flush()
        view = request.GET.get('view', None) or 'default'
        return CreationResponse(first, user_id, permissions, view)


@view_config(context=InstanceContext, request_method='PUT', renderer="json",
             header=JSON_HEADER, ctx_instance_class=UserLanguagePreference)
@view_config(context=InstanceContext, request_method='PATCH', renderer="json",
             header=JSON_HEADER, ctx_instance_class=UserLanguagePreference)
def modify_user_language_preference(request):
    json_data = request.json_body
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = ctx.get_permissions()
    instance = ctx._instance
    if not instance.user_can(user_id, CrudPermissions.UPDATE, permissions):
        raise HTTPUnauthorized()
    try:
        updated = instance.update_from_json(json_data, user_id, ctx)
        view = request.GET.get('view', None) or 'default'
        if view == 'id_only':
            return [updated.uri()]
        else:
            return updated.generic_json(view, user_id, permissions)

    except NotImplementedError:
        raise HTTPNotImplemented()
    except ObjectNotUniqueError as e:
        raise JSONError(str(e), code=409)


@view_config(context=ClassContext, renderer='json',
             ctx_class=AgentProfile, name='autocomplete', permission=P_ADMIN_DISC)
@view_config(context=CollectionContext, renderer='json',
             ctx_collection_class=AgentProfile, name='autocomplete', permission=P_READ)
def participant_autocomplete(request):
    ctx = request.context
    keyword = request.GET.get('q')
    if not keyword:
        raise HTTPBadRequest("please specify search terms (q)")
    limit = request.GET.get('limit', 20)
    try:
        limit = int(limit)
    except:
        raise HTTPBadRequest("limit must be an integer")
    if limit > 100:
        raise HTTPBadRequest("be reasonable")
    query = AgentProfile.default_db.query(
            AgentProfile.id, AgentProfile.name, User.username
        ).outerjoin(User).filter((User.verified == True) | (User.id == None))
    discussion = ctx.get_instance_of_class(Discussion)
    if discussion:
        query = query.filter(AgentProfile.id.in_(
            discussion.get_participants_query(True, True).subquery()))

    if len(keyword) < 6:
        query = query.add_column(literal(0))
        matchstr = '%'.join(keyword)
        matchstr = '%'.join(('', matchstr, ''))
        agents = query.filter(AgentProfile.name.ilike(matchstr) |
                             User.username.ilike(matchstr)
            ).limit(limit * 5).all()
        agents.sort(key=lambda u: max(
            jaro_winkler(u[1], keyword),
            jaro_winkler(u[2], keyword) if u[2] else 0
            ), reverse=True)
        num = min(len(agents), limit)
        agents = agents[:num]
    else:
        matchstr = keyword
        query, rank = add_simple_text_search(
            query, [AgentProfile.name], keyword.split())
        agents = query.order_by(rank.desc()).limit(limit).all()
    return {'results': [{
        'id': AgentProfile.uri_generic(id),
        'text': name} for (id, name, username, rank) in agents]}
