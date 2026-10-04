import io
from datetime import timedelta
from unittest.mock import patch
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from studio.models import Job, Review, Post, BotState, TelegramOutbox
from studio.reviews import issue_invitation, start_review, interact
from studio.integrations import IntegrationError, make_caption
from studio.tasks import advance, dispatch
from studio.telegram import Telegram
pytestmark=pytest.mark.django_db

def photo():
    buffer=io.BytesIO();Image.new('RGB',(400,400),'blue').save(buffer,'PNG')
    return SimpleUploadedFile('test.png',buffer.getvalue(),content_type='image/png')
def create_job(api,automatic=False):
    response=api.post('/api/v1/jobs/',{'title':'Ремонт смесителя','description':'Заменили картридж.',
        'city':'Алматы','photo':photo(),'photo_rights':True,'auto_publish':automatic},format='multipart')
    assert response.status_code==201,response.data
    return Job.objects.get(pk=response.data['id'])
def approve(job,public=True,chat=101):
    review,token=issue_invitation(job)
    assert start_review(token,chat)['stage']=='CONSENT'
    assert interact(review.pk,chat,action='ai_yes')['stage']=='CHATTING'
    for text in ['Смеситель снова работает.','Мастер всё объяснил.','Замечаний нет.']:
        result=interact(review.pk,chat,text=text)
    assert result['stage']=='APPROVAL'
    assert interact(review.pk,chat,action='approve')['stage']=='PUBLIC'
    assert interact(review.pk,chat,action='public_yes' if public else 'public_no')['stage']=='DONE'
    return Review.objects.get(pk=review.pk)
def test_full_demo_pipeline(api):
    job=create_job(api);review=approve(job);post=Post.objects.get(job=job)
    advance(str(post.pk));post.refresh_from_db()
    assert post.status=='DRAFT' and f'«{review.approved_text}»' in post.caption
    assert api.post(f'/api/v1/jobs/{job.pk}/publish/',{},format='json').status_code==202
    with patch('httpx.request',side_effect=AssertionError('no external calls in demo')):advance(str(post.pk))
    post.refresh_from_db()
    assert post.status=='DEMO' and post.media_id.startswith('demo-') and not post.permalink
    assert api.post(f'/api/v1/jobs/{job.pk}/publish/',{},format='json').status_code==400
    advance(str(post.pk));assert Post.objects.count()==1
def test_auto_publication(api):
    job=create_job(api,True);approve(job);post=Post.objects.get(job=job)
    advance(str(post.pk));post.refresh_from_db();assert post.status=='QUEUED'
    advance(str(post.pk));post.refresh_from_db();assert post.status=='DEMO'
def test_private_review_never_generates(api):
    job=create_job(api,True);approve(job,public=False)
    assert not Post.objects.exists()
    assert api.post(f'/api/v1/jobs/{job.pk}/generate/').status_code==400
def test_withdrawal_cancels_before_publish(api):
    job=create_job(api,True);review=approve(job);post=Post.objects.get(job=job)
    advance(str(post.pk));interact(review.pk,101,action='stop');advance(str(post.pk));post.refresh_from_db()
    assert post.status=='CANCELLED'
    review.refresh_from_db();assert not review.public_consent
def test_invitation_hash_binding_expiry_and_replay(api):
    job=create_job(api);review,token=issue_invitation(job)
    assert token not in review.token_hash
    start_review(token,101)
    with pytest.raises(ValidationError):start_review(token,102)
    with pytest.raises(ValidationError):interact(review.pk,102,action='ai_yes')
    interact(review.pk,101,action='ai_yes');interact(review.pk,101,action='ai_yes')
    review.refresh_from_db();assert review.stage=='CHATTING' and not review.answers
    Review.objects.filter(pk=review.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
    with pytest.raises(ValidationError):interact(review.pk,101,text='test')
    assert interact(review.pk,101,action='stop')['stage']=='STOPPED'
def test_same_client_can_review_another_job(api):
    approve(create_job(api));approve(create_job(api))
    assert Review.objects.filter(chat_id=101,stage='DONE').count()==2
def test_owner_isolation_and_private_photos(api):
    job=create_job(api);anonymous=APIClient()
    assert anonymous.get('/api/v1/jobs/').status_code==401
    assert anonymous.get(f'/api/v1/jobs/{job.pk}/photo/').status_code==401
    from django.contrib.auth import get_user_model
    stranger=get_user_model().objects.create_user(username='stranger');other=APIClient();other.force_authenticate(stranger)
    for action in ['photo','invite','demo-chat','publish']:
        response=other.get(f'/api/v1/jobs/{job.pk}/{action}/') if action=='photo' else other.post(f'/api/v1/jobs/{job.pk}/{action}/',{},format='json')
        assert response.status_code==404
    body=api.get('/api/v1/jobs/').data[0];assert 'owner' not in body and 'photo' not in body
    assert api.get(f'/api/v1/jobs/{job.pk}/photo/').status_code==200
    approve(job);post=Post.objects.get(job=job)
    assert anonymous.get(f'/public/photos/{post.media_token}/').status_code==404
def test_photo_validation_and_metadata_stripping(api):
    response=api.post('/api/v1/jobs/',{'title':'bad','description':'test','photo':SimpleUploadedFile('bad.jpg',b'not an image')},format='multipart')
    assert response.status_code==400 and Job.objects.count()==0
    job=create_job(api)
    with Image.open(job.photo.path) as stored:assert stored.format=='JPEG' and not stored.getexif()
def test_disabled_live_publish_and_simulator(api,settings):
    job=create_job(api);approve(job);post=Post.objects.get(job=job);advance(str(post.pk))
    settings.DEMO_MODE=False
    Job.objects.filter(pk=job.pk).update(is_demo=False)
    assert api.post(f'/api/v1/jobs/{job.pk}/demo-chat/',{},format='json').status_code==400
    assert api.post(f'/api/v1/jobs/{job.pk}/publish/',{},format='json').status_code==400
def test_ai_error_rolls_back_answer(api):
    job=create_job(api);review,token=issue_invitation(job)
    start_review(token,101);interact(review.pk,101,action='ai_yes')
    with patch('studio.reviews.next_question',side_effect=IntegrationError('AI unavailable')):
        with pytest.raises(IntegrationError):interact(review.pk,101,text='test')
    review.refresh_from_db();assert review.answers==[] and review.stage=='CHATTING'
def test_caption_preserves_long_review(api):
    job=create_job(api);review=approve(job);review.approved_text='A'*1400;review.save()
    job.description='B'*2000;job.save();caption=make_caption(job)
    assert len(caption)<=2200 and review.approved_text in caption

def live_ready(api,settings):
    job=create_job(api);approve(job);post=Post.objects.get(job=job);advance(str(post.pk))
    settings.DEMO_MODE=False;settings.INSTAGRAM_PUBLISH_ENABLED=True
    Job.objects.filter(pk=job.pk).update(is_demo=False)
    post.status='QUEUED';post.save();return post

def test_live_two_step_and_no_double_publish(api,settings):
    post=live_ready(api,settings)
    with patch('studio.tasks.Instagram') as mock:
        adapter=mock.return_value;adapter.create.return_value='123';adapter.status.return_value='FINISHED'
        adapter.publish.return_value='456';adapter.permalink.return_value='https://www.instagram.com/p/test/'
        advance(str(post.pk));post.refresh_from_db();assert post.status=='WAITING' and post.container_id=='123'
        post.due_at=timezone.now()-timedelta(seconds=1);post.save()
        advance(str(post.pk));advance(str(post.pk));post.refresh_from_db()
        assert post.status=='PUBLISHED' and post.media_id=='456' and adapter.publish.call_count==1

def test_lost_publish_response_is_not_retryable(api,settings):
    post=live_ready(api,settings);post.status='WAITING';post.container_id='123';post.save()
    with patch('studio.tasks.Instagram') as mock:
        mock.return_value.status.return_value='FINISHED';mock.return_value.publish.side_effect=IntegrationError('timeout')
        advance(str(post.pk));advance(str(post.pk));assert mock.return_value.publish.call_count==1
    post.refresh_from_db();assert post.status=='UNCERTAIN'
    assert api.post(f'/api/v1/jobs/{post.job_id}/retry/').status_code==400

def test_permalink_error_does_not_retry_publish(api,settings):
    post=live_ready(api,settings);post.status='WAITING';post.container_id='123';post.save()
    with patch('studio.tasks.Instagram') as mock:
        mock.return_value.status.return_value='FINISHED';mock.return_value.publish.return_value='456'
        mock.return_value.permalink.side_effect=IntegrationError('timeout')
        advance(str(post.pk));advance(str(post.pk));assert mock.return_value.publish.call_count==1
    post.refresh_from_db();assert post.status=='PUBLISHED' and post.media_id=='456'

def test_crashed_publishing_marked_uncertain(api):
    job=create_job(api);approve(job);post=Post.objects.get(job=job)
    post.status='PUBLISHING';post.lease_until=timezone.now()-timedelta(minutes=1);post.save()
    dispatch();post.refresh_from_db();assert post.status=='UNCERTAIN'

def test_telegram_update_dedup_and_private_only(api):
    job=create_job(api);review,token=issue_invitation(job);BotState.objects.create(name='telegram');bot=Telegram()
    update={'update_id':10,'message':{'chat':{'id':101,'type':'private'},'text':'/start '+token}}
    bot.process(update);bot.process(update);assert TelegramOutbox.objects.count()==1
    review.refresh_from_db();assert review.stage=='CONSENT'
    bot.process({'update_id':11,'message':{'chat':{'id':-123,'type':'group'},'text':'/start '+token}})
    assert TelegramOutbox.objects.count()==1 and BotState.objects.get(name='telegram').offset==12

def test_review_cannot_be_forged_by_owner_live(api,settings):
    job=create_job(api);settings.DEMO_MODE=False
    Job.objects.filter(pk=job.pk).update(is_demo=False)
    assert api.post(f'/api/v1/jobs/{job.pk}/demo-chat/',{'action':'public_yes'},format='json').status_code==400
    assert api.patch(f'/api/v1/jobs/{job.pk}/',{'review':{'public_consent':True}},format='json').status_code==405


def test_demo_job_never_becomes_real_after_switch(api,settings):
    job=create_job(api,True);approve(job);post=Post.objects.get(job=job)
    advance(str(post.pk));settings.DEMO_MODE=False;settings.INSTAGRAM_PUBLISH_ENABLED=True
    with patch('studio.tasks.Instagram',side_effect=AssertionError('must not publish demo data')):
        advance(str(post.pk))
    post.refresh_from_db();assert post.status=='DEMO'

def test_rotated_invitation_invalidates_previous_link(api):
    job=create_job(api);review,old=issue_invitation(job);same,new=issue_invitation(job)
    assert review.pk==same.pk and new!=old
    with pytest.raises(ValidationError):start_review(old,101)
    assert start_review(new,101)['stage']=='CONSENT'
    with pytest.raises(ValidationError):issue_invitation(job)

def test_model_refusal_is_safe_and_does_not_log_secrets(settings):
    from studio.integrations import ask_model,Question
    settings.OPENAI_API_KEY='not-a-real-key-for-tests'
    with patch('openai.OpenAI') as mock:
        mock.return_value.responses.parse.return_value.status='completed'
        mock.return_value.responses.parse.return_value.output_parsed=None
        with pytest.raises(IntegrationError) as exc:ask_model(Question,'instructions','data')
    assert settings.OPENAI_API_KEY not in str(exc.value)

def test_instagram_adapter_uses_bearer_and_official_container_api(settings):
    from studio.integrations import Instagram
    from types import SimpleNamespace
    settings.DEMO_MODE=False;settings.INSTAGRAM_PUBLISH_ENABLED=True
    settings.INSTAGRAM_USER_ID='123';settings.INSTAGRAM_ACCESS_TOKEN='test-token'
    settings.PUBLIC_BASE_URL='https://crm.example.com'
    with patch('studio.integrations.httpx.request') as request:
        request.return_value.json.return_value={'id':'456'}
        adapter=Instagram()
        result=adapter.create(SimpleNamespace(media_token='photo-token',caption='Approved caption'))
        assert result=='456'
        args,kwargs=request.call_args
        assert args==('POST','https://graph.instagram.com/v23.0/123/media')
        assert kwargs['headers']['Authorization']=='Bearer test-token'
        assert kwargs['data']['image_url']=='https://crm.example.com/public/photos/photo-token/'
        assert 'test-token' not in args[1] and 'access_token' not in kwargs['data']

@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_generation_once(api):
    from django.db import connection,close_old_connections
    from concurrent.futures import ThreadPoolExecutor
    import threading
    if connection.vendor!='postgresql':pytest.skip('PostgreSQL row-lock test')
    job=create_job(api);approve(job);post=Post.objects.get(job=job)
    barrier=threading.Barrier(2)
    def run():
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            advance(str(post.pk))
        finally:close_old_connections()
    with patch('studio.tasks.make_caption',wraps=make_caption) as caption:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(run) for _ in range(2)]
            for future in futures:future.result(timeout=15)
        assert caption.call_count==1
    post.refresh_from_db();assert post.status=='DRAFT'

def test_real_jwt_login_and_authorized_upload(owner):
    client=APIClient()
    response=client.post('/api/v1/auth/login/',{'username':'tester','password':'OnlyTestPassword2026!'},format='json')
    assert response.status_code==200 and 'access' in response.data and 'refresh' in response.data
    client.credentials(HTTP_AUTHORIZATION='Bearer '+response.data['access'])
    job=create_job(client)
    assert client.get(f'/api/v1/jobs/{job.pk}/').status_code==200
    assert client.get('/api/v1/config/').data['demo_mode'] is True
    refreshed=client.post('/api/v1/auth/refresh/',{'refresh':response.data['refresh']},format='json')
    assert refreshed.status_code==200 and 'access' in refreshed.data

def test_blocked_telegram_chat_does_not_block_other_clients():
    from studio.telegram import TelegramError
    TelegramOutbox.objects.create(update_id=1,chat_id=101,payload={'text':'first'})
    TelegramOutbox.objects.create(update_id=2,chat_id=102,payload={'text':'second'})
    with patch.object(Telegram,'request',side_effect=[TelegramError(403),{}]) as send:
        Telegram().flush()
    assert send.call_count==2 and not TelegramOutbox.objects.exists()
